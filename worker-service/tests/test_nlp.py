from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock
import sys
import uuid

from app.pipeline import nlp


def _query_all(result):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = result
    return query


def test_language_helpers_normalize_and_disambiguate_cyrillic():
    assert nlp._normalize_lang("en-US") == "en"
    assert nlp._normalize_lang("ru-RU") == "ru"
    assert nlp._heuristic_cyrillic_lang("Бұл жүйе деректерді өңдейді") == "kk"
    assert nlp._heuristic_cyrillic_lang("Эта система обрабатывает данные") == "ru"


def test_detect_language_uses_langdetect_and_falls_back(monkeypatch):
    langdetect = ModuleType("langdetect")
    langdetect.detect_langs = lambda _sample: [SimpleNamespace(lang="ru", prob=0.51)]
    monkeypatch.setitem(sys.modules, "langdetect", langdetect)

    assert nlp.detect_language("Эта система анализирует документы") == "ru"
    assert nlp.detect_language("") == nlp.config.default_language


def test_get_spacy_model_caches_loaded_models(monkeypatch):
    spacy = ModuleType("spacy")
    loaded = []
    spacy.load = lambda name: loaded.append(name) or {"model": name}
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setattr(nlp, "_models", {})

    first = nlp._get_spacy_model("en")
    second = nlp._get_spacy_model("en")

    assert first == {"model": nlp.config.spacy_model_en}
    assert second == first
    assert len(loaded) == 1


def test_get_spacy_model_handles_missing_and_unknown_models(monkeypatch):
    spacy = ModuleType("spacy")

    def fail(_name):
        raise OSError("missing model")

    spacy.load = fail
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setattr(nlp, "_models", {})

    assert nlp._get_spacy_model("kk") is None
    assert nlp._get_spacy_model("de") is None


def test_handle_nlp_updates_chunk_languages_and_progress(monkeypatch):
    doc = SimpleNamespace(id=uuid.uuid4())
    chunks = [
        SimpleNamespace(document_id=doc.id, chunk_index=0, text="Battery storage helps resilience", lang=None),
        SimpleNamespace(document_id=doc.id, chunk_index=1, text="Эта система устойчива", lang="ru"),
    ]
    session = MagicMock()
    session.query.side_effect = [_query_all([doc]), _query_all(chunks)]
    statuses = []
    events = []
    monkeypatch.setattr(nlp, "detect_language", lambda text: "en" if "Battery" in text else "ru")
    monkeypatch.setattr(nlp, "is_job_cancelled", lambda _session, _job_id: False)
    monkeypatch.setattr(nlp, "update_job_status", lambda _session, _job_id, status, progress=0: statuses.append((status, progress)))
    monkeypatch.setattr(nlp, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))

    nlp.handle_nlp(session, {"jobId": "job-1", "collectionId": "col-1"})

    assert chunks[0].lang == "en"
    assert chunks[1].lang == "ru"
    assert statuses[0] == ("RUNNING", 0)
    assert statuses[-1] == ("RUNNING", 100)
    assert any("NLP finished: 2 chunks" in message for _level, message in events)
    assert session.commit.call_count >= 1


def test_handle_nlp_warns_when_collection_has_no_chunks(monkeypatch):
    doc = SimpleNamespace(id=uuid.uuid4())
    session = MagicMock()
    session.query.side_effect = [_query_all([doc]), _query_all([])]
    statuses = []
    events = []
    monkeypatch.setattr(nlp, "update_job_status", lambda _session, _job_id, status, progress=0: statuses.append((status, progress)))
    monkeypatch.setattr(nlp, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))

    nlp.handle_nlp(session, {"jobId": "job-1", "collectionId": "col-1"})

    assert ("WARN", "No chunks to process") in events
    assert statuses[-1] == ("RUNNING", 100)
