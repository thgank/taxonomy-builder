from types import ModuleType
import sys

from app.pipeline import term_extraction_spacy


def test_load_spacy_returns_cached_model(monkeypatch):
    spacy = ModuleType("spacy")
    loaded = []
    spacy.load = lambda name: loaded.append(name) or {"model": name}
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setattr(term_extraction_spacy, "_nlp_models", {})

    first = term_extraction_spacy.load_spacy("en")
    second = term_extraction_spacy.load_spacy("en")

    assert first == {"model": term_extraction_spacy.config.spacy_model_en}
    assert second == first
    assert len(loaded) == 1


def test_load_spacy_handles_missing_model_and_unknown_lang(monkeypatch):
    spacy = ModuleType("spacy")

    def fail(_name):
        raise OSError("missing")

    spacy.load = fail
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setattr(term_extraction_spacy, "_nlp_models", {})

    assert term_extraction_spacy.load_spacy("ru") is None
    assert term_extraction_spacy.load_spacy("de") is None

