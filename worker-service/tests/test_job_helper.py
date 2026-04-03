from types import SimpleNamespace
from unittest.mock import MagicMock

from app import job_helper


def _query_first(result):
    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = result
    return query


def test_update_job_status_sets_progress_stage_and_timestamps():
    job = SimpleNamespace(
        status="QUEUED",
        progress=0,
        error_message=None,
        current_stage=None,
        retry_count=0,
        started_at=None,
        finished_at=None,
    )
    session = MagicMock()
    session.query.return_value = _query_first(job)

    job_helper.update_job_status(
        session,
        "job-1",
        "RUNNING",
        progress=25,
        current_stage="terms",
        retry_count=1,
    )

    assert job.status == "RUNNING"
    assert job.progress == 25
    assert job.current_stage == "terms"
    assert job.retry_count == 1
    assert job.started_at is not None
    session.commit.assert_called_once()


def test_update_taxonomy_status_marks_finished_for_terminal_states():
    taxonomy_version = SimpleNamespace(status="RUNNING", finished_at=None)
    session = MagicMock()
    session.query.return_value = _query_first(taxonomy_version)

    job_helper.update_taxonomy_status(session, "tax-1", "READY")

    assert taxonomy_version.status == "READY"
    assert taxonomy_version.finished_at is not None
    session.commit.assert_called_once()


def test_is_job_cancelled_reflects_job_state():
    session = MagicMock()
    session.query.return_value = _query_first(SimpleNamespace(status="CANCELLED"))

    assert job_helper.is_job_cancelled(session, "job-1") is True
