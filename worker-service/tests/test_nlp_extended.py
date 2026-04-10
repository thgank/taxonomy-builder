from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock
import sys

from app.pipeline import nlp


def _query_all(result):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = result
    return query


def test_language_helpers_cover_remaining_normalization_and_detection_paths(monkeypatch):
    assert nlp._normalize_lang("kk-KZ") == "kk"
    assert nlp._normalize_lang("es-ES") == nlp.config.default_language
    assert nlp._heuristic_cyrillic_lang("") == nlp.config.default_language
    assert nlp._heuristic_cyrillic_lang("абвгд жзийк") == "ru"
    assert nlp.detect_language("Әріптері бар мәтін") == "kk"

    langdetect = ModuleType("langdetect")
    langdetect.detect_langs = lambda _sample: [SimpleNamespace(lang="de", prob=0.99)]
    monkeypatch.setitem(sys.modules, "langdetect", langdetect)
    assert nlp.detect_language("dieses system ist neu") == nlp.config.default_language

    langdetect.detect_langs = lambda _sample: (_ for _ in ()).throw(RuntimeError("boom"))
    assert nlp.detect_language("plain english text") == nlp.config.default_language


def test_handle_nlp_cancels_midway_and_commits_progress(monkeypatch):
    doc = SimpleNamespace(id="doc-1")
    chunks = [
        SimpleNamespace(document_id=doc.id, chunk_index=i, text=f"chunk {i}", lang=None)
        for i in range(101)
    ]
    session = MagicMock()
    session.query.side_effect = [_query_all([doc]), _query_all(chunks)]
    statuses = []
    events = []

    monkeypatch.setattr(nlp, "detect_language", lambda _text: "en")
    monkeypatch.setattr(nlp, "update_job_status", lambda _session, _job_id, status, progress=0: statuses.append((status, progress)))
    monkeypatch.setattr(nlp, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(nlp, "is_job_cancelled", lambda _session, _job_id: True)

    nlp.handle_nlp(session, {"jobId": "job-1", "collectionId": "col-1"})

    assert statuses[0] == ("RUNNING", 0)
    assert len(statuses) == 1
    assert events[0] == ("INFO", "NLP preprocessing started")


def test_handle_nlp_commits_every_hundred_chunks(monkeypatch):
    doc = SimpleNamespace(id="doc-2")
    chunks = [
        SimpleNamespace(document_id=doc.id, chunk_index=i, text=f"Battery chunk {i}", lang=None)
        for i in range(100)
    ]
    session = MagicMock()
    session.query.side_effect = [_query_all([doc]), _query_all(chunks)]
    statuses = []

    monkeypatch.setattr(nlp, "detect_language", lambda _text: "en")
    monkeypatch.setattr(nlp, "add_job_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(nlp, "is_job_cancelled", lambda _session, _job_id: False)
    monkeypatch.setattr(nlp, "update_job_status", lambda _session, _job_id, status, progress=0: statuses.append((status, progress)))

    nlp.handle_nlp(session, {"jobId": "job-2", "collectionId": "col-2"})

    assert ("RUNNING", 100) in statuses
    assert session.commit.call_count >= 2
