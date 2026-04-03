from types import ModuleType, SimpleNamespace
from collections import Counter
import sys

from app.pipeline import term_extraction_scoring


def test_normalize_score_map_and_candidate_quality_score_cover_edge_shapes():
    assert term_extraction_scoring.normalize_score_map({"a": 2.0, "b": 4.0}) == {"a": 0.0, "b": 1.0}
    assert term_extraction_scoring.normalize_score_map({"a": 1.0, "b": 1.0}) == {"a": 1.0, "b": 1.0}
    assert term_extraction_scoring.candidate_quality_score("battery storage", 0.8, doc_freq=3, total_docs=5) > 0.6
    assert term_extraction_scoring.candidate_quality_score("kw1", 0.8, doc_freq=1, total_docs=5) < 0.7


def test_frequency_and_refinement_helpers_score_multiword_terms():
    chunks = [
        SimpleNamespace(text="Battery storage improves grid resilience", document_id="doc-1"),
        SimpleNamespace(text="Grid battery storage supports resilience", document_id="doc-2"),
    ]
    terms = ["battery", "battery storage", "grid resilience"]

    token_freq = term_extraction_scoring.compute_token_freq(chunks)
    term_freq = term_extraction_scoring.compute_term_freq(terms, chunks)
    doc_freq = term_extraction_scoring.compute_term_doc_freq(terms, chunks)
    suppressed = term_extraction_scoring.suppress_subsumed_single_tokens(
        {"battery": 0.4, "battery storage": 0.9, "grid resilience": 0.8},
        {"battery": 1, "battery storage": 2, "grid resilience": 2},
    )
    refined = term_extraction_scoring.refine_term_scores(
        {"battery": 0.4, "battery storage": 0.9, "grid resilience": 0.8},
        chunks,
    )

    assert token_freq["battery"] == 2
    assert term_freq["battery storage"] >= 2
    assert doc_freq["battery storage"] == 2
    assert "battery" not in suppressed
    assert list(refined.keys())[0] in {"battery storage", "grid resilience"}


def test_cvalue_pmi_and_deduplicate_terms(monkeypatch):
    rapidfuzz = ModuleType("rapidfuzz")
    rapidfuzz.fuzz = SimpleNamespace(ratio=lambda a, b: 95 if "battery" in a and "battery" in b else 20)
    monkeypatch.setitem(sys.modules, "rapidfuzz", rapidfuzz)

    cvals = term_extraction_scoring.compute_cvalue_scores(
        ["battery", "battery storage", "grid resilience"],
        Counter({"battery": 2, "battery storage": 4, "grid resilience": 3}),
    )
    pmis = term_extraction_scoring.compute_pmi_scores(
        ["battery storage", "grid resilience", "battery"],
        Counter({"battery": 6, "storage": 4, "grid": 5, "resilience": 5}),
    )
    canonical, surface = term_extraction_scoring.deduplicate_terms(
        {"battery storage": 0.9, "battery-storage": 0.88, "grid resilience": 0.8},
        threshold=90,
    )

    assert cvals["battery storage"] > cvals["battery"]
    assert pmis["battery storage"] >= 0.0
    assert "battery storage" in canonical
    assert len(surface["battery storage"]) == 2

