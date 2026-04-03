import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from app import consumer


def test_resolve_job_type_falls_back_to_db():
    job_row = SimpleNamespace(type="FULL_PIPELINE")
    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = job_row
    session = MagicMock()
    session.query.return_value = query

    result = consumer._resolve_job_type(session, {}, "job-1")

    assert result == "FULL_PIPELINE"


def test_on_message_success_routes_to_next_stage(monkeypatch):
    session = MagicMock()
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=1, routing_key="import", exchange="taxonomy")
    properties = SimpleNamespace(headers={})
    updates = []
    events = []
    monkeypatch.setattr(consumer, "get_session", lambda: session)
    monkeypatch.setattr(consumer, "update_job_status", lambda session, job_id, status, **kwargs: updates.append((status, kwargs)))
    monkeypatch.setattr(consumer, "add_job_event", lambda session, job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(consumer, "is_job_cancelled", lambda session, job_id: False)

    consumer._on_message(
        lambda session, msg: None,
        channel,
        method,
        properties,
        json.dumps({"jobId": "job-1", "jobType": "FULL_PIPELINE"}).encode(),
    )

    assert any(status == "RUNNING" and kwargs.get("current_stage") == "import" for status, kwargs in updates)
    channel.basic_publish.assert_called_once()
    channel.basic_ack.assert_called_once_with(delivery_tag=1)
    assert not events


def test_on_message_terminal_stage_marks_success(monkeypatch):
    session = MagicMock()
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=2, routing_key="evaluate", exchange="taxonomy")
    properties = SimpleNamespace(headers={})
    updates = []
    events = []
    released = []
    monkeypatch.setattr(consumer, "get_session", lambda: session)
    monkeypatch.setattr(consumer, "update_job_status", lambda session, job_id, status, **kwargs: updates.append((status, kwargs)))
    monkeypatch.setattr(consumer, "add_job_event", lambda session, job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(consumer, "is_job_cancelled", lambda session, job_id: False)
    monkeypatch.setattr(consumer, "_release_collection_lock", lambda session, job_id: released.append(job_id))

    consumer._on_message(
        lambda session, msg: None,
        channel,
        method,
        properties,
        json.dumps({"jobId": "job-2", "jobType": "FULL_PIPELINE"}).encode(),
    )

    assert any(status == "SUCCESS" and kwargs.get("progress") == 100 for status, kwargs in updates)
    assert released == ["job-2"]
    assert events[-1][1] == "Pipeline completed (terminal stage: evaluate)"
    channel.basic_ack.assert_called_once_with(delivery_tag=2)


def test_on_message_retries_when_handler_fails(monkeypatch):
    session = MagicMock()
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=3, routing_key="terms", exchange="taxonomy")
    properties = SimpleNamespace(headers={})
    updates = []
    events = []
    monkeypatch.setattr(consumer, "get_session", lambda: session)
    monkeypatch.setattr(consumer, "update_job_status", lambda session, job_id, status, **kwargs: updates.append((status, kwargs)))
    monkeypatch.setattr(consumer, "add_job_event", lambda session, job_id, level, message: events.append((level, message)))

    consumer._on_message(
        lambda session, msg: (_ for _ in ()).throw(ValueError("boom")),
        channel,
        method,
        properties,
        json.dumps({"jobId": "job-3", "jobType": "FULL_PIPELINE"}).encode(),
    )

    assert any(status == "RETRYING" and kwargs.get("retry_count") == 1 for status, kwargs in updates)
    channel.basic_publish.assert_called_once()
    channel.basic_ack.assert_called_once_with(delivery_tag=3)
    assert "Worker error" in events[-1][1]


def test_on_message_sends_to_dlq_after_max_retries(monkeypatch):
    session = MagicMock()
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=4, routing_key="terms", exchange="taxonomy")
    properties = SimpleNamespace(headers={"x-retry-count": consumer.MAX_RETRIES})
    updates = []
    dlq_calls = []
    releases = []
    monkeypatch.setattr(consumer, "get_session", lambda: session)
    monkeypatch.setattr(consumer, "update_job_status", lambda session, job_id, status, **kwargs: updates.append((status, kwargs)))
    monkeypatch.setattr(consumer, "add_job_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(consumer, "_log_to_dlq", lambda *args: dlq_calls.append(args))
    monkeypatch.setattr(consumer, "_release_collection_lock", lambda session, job_id: releases.append(job_id))

    consumer._on_message(
        lambda session, msg: (_ for _ in ()).throw(RuntimeError("fatal")),
        channel,
        method,
        properties,
        json.dumps({"jobId": "job-4", "jobType": "FULL_PIPELINE"}).encode(),
    )

    assert dlq_calls
    assert releases == ["job-4"]
    assert any(status == "FAILED" and "Max retries exhausted" in kwargs.get("error_message", "") for status, kwargs in updates)
    channel.basic_nack.assert_called_once_with(delivery_tag=4, requeue=False)
