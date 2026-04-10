from collections import Counter

import pytest

from app.pipeline.taxonomy_build import edge_filters


def test_parent_validation_helpers_cover_phrase_and_verbish_paths():
    concept_doc_freq = {
        "energy systems": 10,
        "for energy": 10,
        "runing tested": 10,
        "tiny": 1,
        "one two three four five six": 10,
    }

    assert edge_filters.parent_validity_score("", concept_doc_freq) == 0.0
    assert edge_filters.parent_validity_score("около", concept_doc_freq) == 0.0
    assert edge_filters.parent_validity_score("в том числе energy", concept_doc_freq) < 0.6
    assert edge_filters.parent_validity_score("for energy", concept_doc_freq) < 0.9
    assert edge_filters.parent_validity_score("tiny", concept_doc_freq) < 1.0
    assert edge_filters.parent_validity_score("runing tested", concept_doc_freq) < 0.7
    assert edge_filters.parent_validity_score("one two three four five six", concept_doc_freq) < 1.0
    assert edge_filters.parent_validity_score("also", {"also": 10}) < 0.5

    assert edge_filters.is_valid_parent_label("", concept_doc_freq) is False
    assert edge_filters.is_valid_parent_label("около", concept_doc_freq) is False
    assert edge_filters.is_valid_parent_label("в том числе energy", concept_doc_freq) is False
    assert edge_filters.is_valid_parent_label("abc", {"abc": 0}) is False
    assert edge_filters.is_valid_parent_label("also energy", concept_doc_freq) is False
    assert edge_filters.is_valid_parent_label("also", {"also": 10}) is False
    assert edge_filters.is_valid_parent_label("energy", {"energy": 0}) is False
    assert edge_filters.is_valid_parent_label("runing tested", concept_doc_freq) is False
    assert edge_filters.is_valid_parent_label("energy systems", concept_doc_freq) is True


def test_semantic_and_evidence_helpers_handle_dict_and_non_dict_values():
    edge = {
        "evidence": {
            "semantic_similarity": 0.64,
            "lexical_similarity": 0.20,
            "cooccurrence_support": 0.10,
        }
    }
    noisy = {"evidence": ["bad", {"similarity": 0.55, "lexical_similarity": 0.21}]}

    assert edge_filters.semantic_from_evidence(edge) == 0.64
    assert edge_filters.semantic_from_evidence(noisy) == 0.0
    assert edge_filters.evidence_max_value(noisy, "lexical_similarity") == 0.21
    assert edge_filters.evidence_max_value({"evidence": "oops"}, "similarity") == 0.0


def test_edge_rejection_reason_covers_main_and_recovery_paths(monkeypatch):
    monkeypatch.setattr(edge_filters, "is_low_quality_label", lambda label: label == "kw")
    concept_doc_freq = {
        "energy systems": 10,
        "for energy": 10,
        "battery storage": 6,
        "kw": 5,
        "single": 5,
        "other": 4,
        "component": 7,
        "anchor": 7,
        "hearst parent": 7,
        "word word word word": 7,
    }

    assert edge_filters.edge_rejection_reason(
        {"hypernym": "for", "hyponym": "battery storage", "score": 0.9, "evidence": {"method": "hearst"}},
        concept_doc_freq,
        0.5,
    ) == "invalid_parent_label"

    monkeypatch.setattr(edge_filters, "parent_validity_score", lambda label, _freq: 0.3 if label == "for energy" else 0.9)
    assert edge_filters.edge_rejection_reason(
        {"hypernym": "for energy", "hyponym": "battery storage", "score": 0.9, "evidence": {"method": "hearst"}},
        concept_doc_freq,
        0.5,
    ) == "low_parent_validity"
    monkeypatch.setattr(edge_filters, "parent_validity_score", lambda _label, _freq: 0.9)

    assert edge_filters.edge_rejection_reason(
        {"hypernym": "energy systems", "hyponym": "kw", "score": 0.9, "evidence": {"method": "hearst"}},
        concept_doc_freq,
        0.5,
    ) == "low_quality_label"

    assert edge_filters.edge_rejection_reason(
        {"hypernym": "single", "hyponym": "other", "score": 0.65, "evidence": {"method": "hearst"}},
        concept_doc_freq,
        0.5,
    ) == "single_to_single"

    assert edge_filters.edge_rejection_reason(
        {"hypernym": "word word word word", "hyponym": "x", "score": 0.8, "evidence": {"method": "hearst"}},
        concept_doc_freq,
        0.5,
    ) == "parent_too_long"

    assert edge_filters.edge_rejection_reason(
        {
            "hypernym": "energy systems",
            "hyponym": "battery storage",
            "score": 0.7,
            "evidence": {"method": "hearst", "semantic_similarity": 0.20, "similarity": 0.0},
        },
        concept_doc_freq,
        0.5,
    ) == "low_semantic_evidence"

    assert edge_filters.edge_rejection_reason(
        {
            "hypernym": "component",
            "hyponym": "battery storage",
            "score": 0.70,
            "evidence": {"method": "component_bridge", "semantic_similarity": 0.20},
        },
        concept_doc_freq,
        0.5,
    ) is None

    assert edge_filters.edge_rejection_reason(
        {
            "hypernym": "anchor",
            "hyponym": "battery storage",
            "score": 0.61,
            "evidence": {"method": "component_anchor_bridge", "semantic_similarity": 0.20, "similarity": 0.70, "lexical_similarity": 0.30},
        },
        concept_doc_freq,
        0.5,
    ) is None

    assert edge_filters.edge_rejection_reason(
        {
            "hypernym": "hearst parent",
            "hyponym": "battery storage",
            "score": 0.57,
            "evidence": {"method": "hearst", "semantic_similarity": 0.20, "similarity": 0.20},
        },
        concept_doc_freq,
        0.5,
    ) is None

    assert edge_filters.edge_rejection_reason(
        {
            "hypernym": "single",
            "hyponym": "other",
            "score": 0.60,
            "evidence": {"method": "component_anchor_bridge", "similarity": 0.7, "lexical_similarity": 0.3},
        },
        concept_doc_freq,
        0.5,
        recovery_mode=True,
    ) is None

    assert edge_filters.edge_rejection_reason(
        {
            "hypernym": "energy systems",
            "hyponym": "battery storage",
            "score": 0.60,
            "evidence": {"method": "component_anchor_bridge", "semantic_similarity": 0.20, "similarity": 0.60, "lexical_similarity": 0.15},
        },
        concept_doc_freq,
        0.5,
        recovery_mode=True,
    ) is None

    assert edge_filters.edge_rejection_reason(
        {
            "hypernym": "energy systems",
            "hyponym": "battery storage",
            "score": 0.60,
            "evidence": {"method": "connectivity_repair_fallback", "semantic_similarity": 0.30, "similarity": 0.70, "lexical_similarity": 0.30},
        },
        concept_doc_freq,
        0.5,
        recovery_mode=True,
    ) is None


def test_plausibility_connectivity_and_reason_formatting():
    edge = {
        "hypernym": "energy systems",
        "hyponym": "battery storage",
        "score": 0.7,
        "evidence": {"method": "component_bridge", "semantic_similarity": 0.7},
    }
    freq = {"energy systems": 10, "battery storage": 5}

    assert edge_filters.is_edge_plausible(edge, freq, min_score=0.5) is True
    assert edge_filters.connectivity_min_score(edge, 0.6, recovery_mode=False) == 0.6
    assert edge_filters.connectivity_min_score({"evidence": {"method": "hearst"}}, 0.6, recovery_mode=True) == 0.6
    assert edge_filters.connectivity_min_score(edge, 0.6, recovery_mode=True) == pytest.approx(0.55)
    assert edge_filters.format_reason_counts(Counter()) == "none"
    assert edge_filters.format_reason_counts(Counter({"a": 3, "b": 1})) == "a=3, b=1"
