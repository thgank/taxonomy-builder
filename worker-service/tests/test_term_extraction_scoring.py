"""
Unit tests for term extraction scoring helpers.
"""
from app.pipeline.term_extraction_scoring import (
    candidate_quality_score,
    normalize_score_map,
    suppress_subsumed_single_tokens,
)


class _Chunk:
    def __init__(self, document_id: str, text: str):
        self.document_id = document_id
        self.text = text


class TestNormalizeScoreMap:
    def test_returns_empty_map_for_empty_input(self):
        assert normalize_score_map({}) == {}

    def test_normalizes_relative_range(self):
        result = normalize_score_map({"a": 2.0, "b": 6.0, "c": 10.0})
        assert result["a"] == 0.0
        assert result["c"] == 1.0


class TestCandidateQualityScore:
    def test_prefers_multiword_terms_with_good_document_frequency(self):
        phrase_score = candidate_quality_score(
            "commercial bank",
            base_norm_score=0.8,
            doc_freq=4,
            total_docs=5,
        )
        single_score = candidate_quality_score(
            "bank",
            base_norm_score=0.8,
            doc_freq=4,
            total_docs=5,
        )
        assert phrase_score > single_score


class TestSuppressSubsumedSingleTokens:
    def test_removes_weak_single_tokens_subsumed_by_multiword_terms(self):
        scores = {
            "bank": 0.8,
            "commercial bank": 0.9,
            "retail bank": 0.85,
        }
        term_doc_freq = {
            "bank": 2,
            "commercial bank": 3,
            "retail bank": 2,
        }

        result = suppress_subsumed_single_tokens(scores, term_doc_freq)

        assert "bank" not in result
        assert "commercial bank" in result
        assert "retail bank" in result
