"""
Job helper — update progress, add events, transition statuses.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db import Job, JobEvent, TaxonomyVersion, get_session
from app.logger import get_logger

log = get_logger(__name__)


def update_job_status(
    session: Session,
    job_id: str,
    status: str,
    progress: int | None = None,
    error_message: str | None = None,
    current_stage: str | None = None,
    retry_count: int | None = None,
) -> None:
    job = session.query(Job).filter(Job.id == job_id).first()
    if not job:
        log.warning("Job %s not found", job_id)
        return

    job.status = status
    if progress is not None:
        job.progress = progress
    if error_message:
        job.error_message = error_message
    if current_stage:
        job.current_stage = current_stage
    if retry_count is not None:
        job.retry_count = retry_count

    now = datetime.now(timezone.utc)
    if status == "RUNNING" and not job.started_at:
        job.started_at = now
    if status in ("SUCCESS", "FAILED", "CANCELLED"):
        job.finished_at = now

    session.commit()
    log.info(
        "Job %s → %s (progress=%s, stage=%s, retries=%s)",
        job_id, status, progress, current_stage, retry_count,
    )


def add_job_event(
    session: Session,
    job_id: str,
    level: str,
    message: str,
    meta: dict[str, Any] | None = None,
) -> None:
    event = JobEvent(
        id=uuid.uuid4(),
        job_id=job_id,
        ts=datetime.now(timezone.utc),
        level=level,
        message=message,
        meta=meta or {},
    )
    session.add(event)
    session.commit()


def update_taxonomy_status(
    session: Session,
    taxonomy_version_id: str,
    status: str,
) -> None:
    tv = session.query(TaxonomyVersion).filter(
        TaxonomyVersion.id == taxonomy_version_id
    ).first()
    if tv:
        tv.status = status
        if status in ("READY", "FAILED"):
            tv.finished_at = datetime.now(timezone.utc)
        session.commit()


def is_job_cancelled(session: Session, job_id: str) -> bool:
    job = session.query(Job).filter(Job.id == job_id).first()
    return job is not None and job.status == "CANCELLED"
