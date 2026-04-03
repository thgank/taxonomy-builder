from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

from app.pipeline import ingestion


def _query_all(result):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = result
    return query


def _delete_query():
    query = MagicMock()
    query.filter.return_value = query
    query.delete.return_value = 1
    return query


def test_extract_text_html_and_plain_strip_noise(tmp_path):
    html_path = tmp_path / "sample.html"
    html_path.write_text("<html><body><header>Header</header><p>Hello</p><script>x</script></body></html>", encoding="utf-8")
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("plain content", encoding="utf-8")

    assert ingestion.extract_text_html(str(html_path)) == "Hello"
    assert ingestion.extract_text_plain(str(txt_path)) == "plain content"


def test_handle_import_returns_when_no_new_documents(monkeypatch):
    session = MagicMock()
    session.query.return_value = _query_all([])
    statuses = []
    events = []
    monkeypatch.setattr(ingestion, "update_job_status", lambda _session, _job_id, status, progress=0: statuses.append((status, progress)))
    monkeypatch.setattr(ingestion, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(ingestion, "config", SimpleNamespace(chunk_size=200, chunk_min_chars=20))

    ingestion.handle_import(session, {"jobId": "job-1", "collectionId": "col-1"})

    assert statuses[0] == ("RUNNING", 0)
    assert statuses[-1] == ("RUNNING", 100)
    assert events[-1] == ("WARN", "No NEW documents to process")


def test_handle_import_parses_document_with_plaintext_fallback(monkeypatch, tmp_path):
    doc = SimpleNamespace(
        id=uuid.uuid4(),
        storage_path="docs/report.unknown",
        filename="report.unknown",
        mime_type="application/octet-stream",
        status="NEW",
        parsed_at=None,
    )
    session = MagicMock()
    session.query.side_effect = [_query_all([doc]), _delete_query()]
    added = []
    events = []
    monkeypatch.setattr(ingestion, "is_job_cancelled", lambda _session, _job_id: False)
    monkeypatch.setattr(ingestion, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(ingestion, "update_job_status", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingestion, "extract_text_plain", lambda _filepath: "Source: test\n\nBattery storage improves resilience.")
    monkeypatch.setattr(ingestion, "config", SimpleNamespace(
        chunk_size=80,
        chunk_min_chars=10,
        storage_path=str(tmp_path),
        allow_plaintext_fallback=True,
        strip_document_headers=True,
    ))
    monkeypatch.setattr(session, "add", lambda row: added.append(row))

    ingestion.handle_import(session, {"jobId": "job-1", "collectionId": "col-1"})

    assert doc.status == "PARSED"
    assert doc.parsed_at is not None
    assert added
    assert any(level == "INFO" and "Parsed report.unknown" in message for level, message in events)


def test_handle_import_marks_failed_for_empty_text_and_exceptions(monkeypatch, tmp_path):
    empty_doc = SimpleNamespace(
        id=uuid.uuid4(),
        storage_path="docs/empty.txt",
        filename="empty.txt",
        mime_type="text/plain",
        status="NEW",
        parsed_at=None,
    )
    failing_doc = SimpleNamespace(
        id=uuid.uuid4(),
        storage_path="docs/broken.pdf",
        filename="broken.pdf",
        mime_type="application/pdf",
        status="NEW",
        parsed_at=None,
    )
    session = MagicMock()
    session.query.side_effect = [_query_all([empty_doc, failing_doc]), _delete_query()]
    events = []

    def pdf_extractor(_filepath):
        raise RuntimeError("pdf broken")

    monkeypatch.setattr(ingestion, "is_job_cancelled", lambda _session, _job_id: False)
    monkeypatch.setattr(ingestion, "extract_text_plain", lambda _filepath: "   ")
    monkeypatch.setattr(ingestion, "extract_text_pdf", pdf_extractor)
    monkeypatch.setattr(ingestion, "config", SimpleNamespace(
        chunk_size=80,
        chunk_min_chars=10,
        storage_path=str(tmp_path),
        allow_plaintext_fallback=False,
        strip_document_headers=True,
    ))
    monkeypatch.setattr(ingestion, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(ingestion, "update_job_status", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingestion, "EXTRACTORS", {
        "text/plain": ingestion.extract_text_plain,
        "application/pdf": ingestion.extract_text_pdf,
    })

    ingestion.handle_import(session, {"jobId": "job-1", "collectionId": "col-1"})

    assert empty_doc.status == "FAILED"
    assert failing_doc.status == "FAILED"
    assert any(level == "WARN" and "Empty text extracted from empty.txt" in message for level, message in events)
    assert any(level == "ERROR" and "Failed to parse broken.pdf" in message for level, message in events)


def test_handle_import_handles_cancellation_and_unsupported_mime(monkeypatch, tmp_path):
    cancelled_doc = SimpleNamespace(
        id=uuid.uuid4(),
        storage_path="docs/cancel.txt",
        filename="cancel.txt",
        mime_type="text/plain",
        status="NEW",
        parsed_at=None,
    )
    unsupported_doc = SimpleNamespace(
        id=uuid.uuid4(),
        storage_path="docs/unsupported.bin",
        filename="unsupported.bin",
        mime_type="application/octet-stream",
        status="NEW",
        parsed_at=None,
    )
    events = []

    session = MagicMock()
    session.query.return_value = _query_all([cancelled_doc])
    monkeypatch.setattr(ingestion, "is_job_cancelled", lambda _session, _job_id: True)
    monkeypatch.setattr(ingestion, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(ingestion, "update_job_status", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingestion, "config", SimpleNamespace(
        chunk_size=80,
        chunk_min_chars=10,
        storage_path=str(tmp_path),
        allow_plaintext_fallback=False,
        strip_document_headers=True,
    ))

    ingestion.handle_import(session, {"jobId": "job-1", "collectionId": "col-1"})

    assert ("WARN", "Job cancelled during import") in events

    session = MagicMock()
    session.query.side_effect = [_query_all([unsupported_doc])]
    events = []
    monkeypatch.setattr(ingestion, "is_job_cancelled", lambda _session, _job_id: False)
    monkeypatch.setattr(ingestion, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))

    ingestion.handle_import(session, {"jobId": "job-2", "collectionId": "col-1"})

    assert unsupported_doc.status == "FAILED"
    assert any("Unsupported MIME type for unsupported.bin" in message for _level, message in events)
