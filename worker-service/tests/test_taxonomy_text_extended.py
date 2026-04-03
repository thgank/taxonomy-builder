from types import ModuleType, SimpleNamespace
import sys

from app.pipeline import taxonomy_text


def _token(text, pos, lemma=None, is_punct=False, is_space=False):
    return SimpleNamespace(text=text, pos_=pos, lemma_=(lemma or text.lower()), is_punct=is_punct, is_space=is_space)


def test_load_spacy_noun_phrase_checks_and_fuzzy_matching(monkeypatch):
    spacy = ModuleType("spacy")
    spacy.load = lambda _name: (lambda text: [_token("energy", "NOUN"), _token("system", "NOUN")])
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setattr(taxonomy_text, "_NLP_MODELS", {})

    model = taxonomy_text._load_spacy("en")
    assert model is not None
    assert taxonomy_text._is_noun_phrase_candidate("energy system", model) is True
    assert taxonomy_text._is_noun_phrase_candidate("for", None, allow_single=True) is False
    assert taxonomy_text.find_closest_concept("battery energy systems", {"battery energy system", "finance platform"}) == "battery energy system"


def test_extract_hearst_pairs_supports_hard_and_soft_modes(monkeypatch):
    chunk = SimpleNamespace(
        id="chunk-1",
        text="Energy system such as battery energy system and solar energy system.",
    )
    concept_set = {"energy system", "battery energy system", "solar energy system"}
    monkeypatch.setattr(taxonomy_text, "_load_spacy", lambda _lang: None)

    hard = taxonomy_text.extract_hearst_pairs([chunk], concept_set, lang="en", soft_mode=False)
    soft = taxonomy_text.extract_hearst_pairs([chunk], concept_set, lang="en", soft_mode=True)

    assert len(hard) >= 1
    assert len(soft) >= len(hard)
    assert all(edge["evidence"]["method"] == "hearst" for edge in soft)


def test_extract_hearst_trigger_pairs_uses_doc_frequency_and_trigger_hints():
    chunk = SimpleNamespace(
        id="chunk-2",
        text="Energy system including battery energy system and solar energy system improves resilience.",
    )
    pairs = taxonomy_text.extract_hearst_trigger_pairs(
        [chunk],
        {"energy system", "battery energy system", "solar energy system"},
        lang="en",
        concept_doc_freq={"energy system": 8, "battery energy system": 3, "solar energy system": 3},
        max_pairs=3,
    )

    assert pairs
    assert pairs[0]["hypernym"] == "energy system"
    assert pairs[0]["evidence"]["method"] == "hearst_trigger_fallback"
