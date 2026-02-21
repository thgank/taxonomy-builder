"""
RabbitMQ consumer — listens on all pipeline queues and dispatches to handlers.
Stage-aware routing with exponential backoff retries + DLQ logging.
"""
from __future__ import annotations

import json
import uuid
import functools
from datetime import datetime, timezone
from typing import Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel

from app.config import config
from app.logger import get_logger
from app.db import get_session, DeadLetterLog
from app.job_helper import update_job_status, add_job_event, is_job_cancelled

log = get_logger(__name__)

MAX_RETRIES = 5

# ── Stage routing map ────────────────────────────────────
# Maps job_type → ordered list of routing keys
STAGE_MAP: dict[str, list[str]] = {
    "FULL_PIPELINE": ["import", "nlp", "terms", "build", "evaluate"],
    "IMPORT":        ["import"],
    "NLP":           ["nlp"],
    "TERMS":         ["terms"],
    "TAXONOMY":      ["build"],
    "EVALUATE":      ["evaluate"],
}


def _resolve_next_routing_key(job_type: str, current_routing_key: str) -> str | None:
    """
    Determine the next routing key based on job type and current stage.
    Returns None if this is the terminal stage.
    """
    stages = STAGE_MAP.get(job_type, [])
    try:
        idx = stages.index(current_routing_key)
    except ValueError:
        return None
    if idx + 1 < len(stages):
        return stages[idx + 1]
    return None


def _resolve_job_type(session, msg: dict, job_id: str | None) -> str | None:
    """Resolve job type from message first, then DB fallback."""
    job_type = msg.get("jobType") or msg.get("job_type")
    if job_type:
        return str(job_type)

    if not job_id:
        return None

    from app.db import Job

    job = session.query(Job).filter(Job.id == job_id).first()
    if job and job.type:
        return str(job.type)
    return None


def _safe_parse_message(body: bytes) -> dict | None:
    """Safely parse JSON message, returning None on failure."""
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        log.error("Failed to parse message body: %s", exc)
        return None


def _log_to_dlq(session, job_id: str | None, queue_name: str,
                routing_key: str, payload: dict, error_message: str,
                retry_count: int) -> None:
    """Persist a dead-letter record for observability."""
    try:
        entry = DeadLetterLog(
            id=uuid.uuid4(),
            job_id=job_id,
            queue_name=queue_name,
            routing_key=routing_key,
            payload=payload,
            error_message=str(error_message)[:4000],
            retry_count=retry_count,
            created_at=datetime.now(timezone.utc),
        )
        session.add(entry)
        session.commit()
    except Exception as dlq_exc:
        log.error("Failed to write DLQ log: %s", dlq_exc)


def _on_message(
    handler: Callable,
    channel: BlockingChannel,
    method: pika.spec.Basic.Deliver,
    properties: pika.BasicProperties,
    body: bytes,
) -> None:
    """Generic callback wrapper with stage-aware routing, retry + DLQ."""
    msg = _safe_parse_message(body)
    if msg is None:
        # Unparseable message → reject immediately to DLQ
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    job_id = msg.get("jobId") or msg.get("job_id")
    correlation_id = msg.get("correlationId") or msg.get("correlation_id", "")

    # We may need DB fallback to resolve job_type.
    job_type = msg.get("jobType") or msg.get("job_type", "")

    log.info(
        "Received message on %s — job=%s type=%s corr=%s",
        method.routing_key, job_id, job_type, correlation_id,
        extra={"job_id": job_id, "correlation_id": correlation_id},
    )

    session = get_session()
    try:
        resolved_job_type = _resolve_job_type(session, msg, job_id)
        if not resolved_job_type or resolved_job_type not in STAGE_MAP:
            raise ValueError(
                f"Missing or unsupported jobType '{resolved_job_type}' for job={job_id}"
            )

        # Keep stage metadata consistent even if handler exits early.
        if job_id:
            update_job_status(
                session, job_id, "RUNNING",
                current_stage=method.routing_key,
            )

        handler(session, msg)

        # Respect cancellation: do not route or finalize as SUCCESS.
        if job_id and is_job_cancelled(session, job_id):
            add_job_event(
                session, job_id, "INFO",
                f"Stage '{method.routing_key}' stopped: job already cancelled",
            )
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        # ── Stage-aware routing: determine next step from job_type ──
        next_routing_key = _resolve_next_routing_key(
            resolved_job_type, method.routing_key
        )
        if next_routing_key:
            channel.basic_publish(
                exchange=config.exchange,
                routing_key=next_routing_key,
                body=body,
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                ),
            )
            log.info(
                "Published next step → %s (job_type=%s)",
                next_routing_key, resolved_job_type,
            )
        else:
            # Terminal stage — mark job SUCCESS and release collection lock
            if job_id:
                try:
                    update_job_status(
                        session, job_id, "SUCCESS",
                        progress=100,
                        current_stage=method.routing_key,
                    )
                    add_job_event(session, job_id, "INFO",
                                  f"Pipeline completed (terminal stage: {method.routing_key})")
                    # Release active_job on collection
                    _release_collection_lock(session, job_id)
                except Exception:
                    log.error("Failed to finalize job %s", job_id, exc_info=True)

        channel.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        session.rollback()
        retry_count = (properties.headers or {}).get("x-retry-count", 0)
        log.error(
            "Error processing message (retry %d/%d): %s",
            retry_count, MAX_RETRIES, exc,
            extra={"job_id": job_id},
        )

        if job_id:
            try:
                add_job_event(
                    session, job_id, "ERROR",
                    f"Worker error (attempt {retry_count + 1}/{MAX_RETRIES}): {exc}",
                )
                if retry_count < MAX_RETRIES:
                    update_job_status(
                        session, job_id, "RETRYING",
                        current_stage=method.routing_key,
                        retry_count=retry_count + 1,
                    )
            except Exception:
                pass

        if retry_count < MAX_RETRIES:
            # Non-blocking retry: republish immediately with retry header.
            log.info("Retrying now (attempt %d/%d)", retry_count + 1, MAX_RETRIES)

            headers = dict(properties.headers or {})
            headers["x-retry-count"] = retry_count + 1
            channel.basic_publish(
                exchange=config.exchange,
                routing_key=method.routing_key,
                body=body,
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                    headers=headers,
                ),
            )
            channel.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Exhausted retries → NACK to RabbitMQ DLQ + log to DB
            log.error("Max retries exhausted for job %s — sending to DLQ", job_id)
            _log_to_dlq(
                session, str(job_id) if job_id else None,
                method.exchange, method.routing_key,
                msg, str(exc), retry_count,
            )
            if job_id:
                try:
                    update_job_status(
                        session, job_id, "FAILED",
                        error_message=f"Max retries exhausted: {exc}",
                        current_stage=method.routing_key,
                        retry_count=retry_count,
                    )
                    _release_collection_lock(session, job_id)
                except Exception:
                    pass
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        session.close()


def _release_collection_lock(session, job_id: str) -> None:
    """Clear active_job_id on the collection when job finishes."""
    from app.db import Job, Collection
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if job and job.collection_id:
            col = session.query(Collection).filter(
                Collection.id == job.collection_id
            ).first()
            if col and str(col.active_job_id) == str(job_id):
                col.active_job_id = None
                session.commit()
    except Exception as exc:
        log.error("Failed to release collection lock for job %s: %s", job_id, exc)


def start_consumer(handlers: dict[str, Callable]) -> None:
    """
    Start blocking consumer.

    handlers: dict mapping queue_name → handler_fn
    """
    params = pika.URLParameters(config.rabbitmq_url)
    params.heartbeat = 600
    params.blocked_connection_timeout = 300

    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)

    for queue_name, handler_fn in handlers.items():
        callback = functools.partial(_on_message, handler_fn)
        channel.basic_consume(queue=queue_name, on_message_callback=callback)
        log.info("Consuming from %s", queue_name)

    log.info("Worker consumer started — waiting for messages...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("Shutting down consumer")
        channel.stop_consuming()
    finally:
        connection.close()
