"""
RabbitMQ consumer — listens on all pipeline queues and dispatches to handlers.
Idempotent processing with retries + DLQ.
"""
from __future__ import annotations

import json
import functools
import traceback
from typing import Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel

from app.config import config
from app.logger import get_logger
from app.db import get_session
from app.job_helper import update_job_status, add_job_event

log = get_logger(__name__)

MAX_RETRIES = 5


def _on_message(
    handler: Callable,
    next_routing_key: str | None,
    channel: BlockingChannel,
    method: pika.spec.Basic.Deliver,
    properties: pika.BasicProperties,
    body: bytes,
) -> None:
    """Generic callback wrapper with retry / DLQ logic."""
    msg: dict = json.loads(body)
    job_id = msg.get("jobId") or msg.get("job_id")
    correlation_id = msg.get("correlationId") or msg.get("correlation_id", "")

    log.info(
        "Received message on %s — job=%s corr=%s",
        method.routing_key, job_id, correlation_id,
        extra={"job_id": job_id, "correlation_id": correlation_id},
    )

    session = get_session()
    try:
        handler(session, msg)

        # If there's a next step, publish continuation
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
            log.info("Published next step → %s", next_routing_key)

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
                    f"Worker error (attempt {retry_count + 1}): {exc}",
                )
            except Exception:
                pass

        if retry_count < MAX_RETRIES:
            # Re-publish with incremented retry header
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
            # Exhausted retries → NACK to DLQ
            log.error("Max retries exhausted for job %s — sending to DLQ", job_id)
            if job_id:
                try:
                    update_job_status(session, job_id, "FAILED",
                                      error_message=str(exc))
                except Exception:
                    pass
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        session.close()


def start_consumer(handlers: dict[str, tuple[Callable, str | None]]) -> None:
    """
    Start blocking consumer.

    handlers: dict mapping queue_name → (handler_fn, next_routing_key | None)
    """
    params = pika.URLParameters(config.rabbitmq_url)
    params.heartbeat = 600
    params.blocked_connection_timeout = 300

    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)

    for queue_name, (handler_fn, next_rk) in handlers.items():
        callback = functools.partial(_on_message, handler_fn, next_rk)
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
