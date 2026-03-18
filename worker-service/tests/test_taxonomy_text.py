"""
Unit tests for taxonomy text normalization and fuzzy concept matching.
"""
from app.pipeline.taxonomy_text import (
    find_closest_concept,
    is_low_quality_label,
    normalize_candidate,
    split_enumeration,
)


class TestNormalizeCandidate:
    def test_filters_generic_single_terms(self):
        assert normalize_candidate("type") is None

    def test_normalizes_spacing_and_case(self):
        assert normalize_candidate("  Commercial   BANK  ") == "commercial bank"


class TestLowQualityLabel:
    def test_detects_noise_like_identifiers(self):
        assert is_low_quality_label("kw") is True

    def test_accepts_meaningful_domain_term(self):
        assert is_low_quality_label("commercial bank") is False


class TestSplitEnumeration:
    def test_splits_multiple_connectors(self):
        result = split_enumeration("bank, insurance or lending")
        assert result == ["bank", "insurance", "lending"]


class TestFindClosestConcept:
    def test_returns_best_match_by_token_overlap(self):
        concept = find_closest_concept(
            "commercial bank services",
            {"retail bank", "commercial bank", "loan portfolio"},
        )
        assert concept == "commercial bank"

    def test_returns_none_when_match_is_too_weak(self):
        concept = find_closest_concept(
            "astronomy",
            {"retail bank", "commercial bank", "loan portfolio"},
        )
        assert concept is None
