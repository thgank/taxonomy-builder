from collections import Counter

from app.pipeline.taxonomy_build.edge_filters import (
    connectivity_min_score,
    edge_rejection_reason,
    evidence_max_value,
    format_reason_counts,
    is_valid_parent_label,
    parent_validity_score,
    semantic_from_evidence,
)


def test_parent_validity_score_and_is_valid_parent_label_filter_bad_parents():
    concept_doc_freq = {"energy": 10, "for": 10, "runing": 10}

    assert parent_validity_score("energy", concept_doc_freq) > 0.5
    assert parent_validity_score("for", concept_doc_freq) < 0.5
    assert is_valid_parent_label("energy", concept_doc_freq) is True
    assert is_valid_parent_label("for", concept_doc_freq) is False


def test_semantic_helpers_extract_best_values_from_evidence():
    edge = {
        "evidence": [
            {"semantic_similarity": 0.62, "lexical_similarity": 0.2, "cooccurrence_support": 0.1},
            {"cosine_similarity": 0.74, "retrieval_evidence_score": 0.7},
        ]
    }

    assert semantic_from_evidence(edge) >= 0.74
    assert evidence_max_value(edge, "lexical_similarity") == 0.2


def test_edge_rejection_reason_covers_invalid_parent_and_low_score_paths():
    concept_doc_freq = {"for": 10, "energy": 10}
    invalid_parent = {"hypernym": "for", "hyponym": "battery storage", "score": 0.9, "evidence": {"method": "hearst"}}
    weak_score = {"hypernym": "energy", "hyponym": "battery storage", "score": 0.2, "evidence": {"method": "hearst"}}

    assert edge_rejection_reason(invalid_parent, concept_doc_freq, min_score=0.5) == "invalid_parent_label"
    assert edge_rejection_reason(weak_score, concept_doc_freq, min_score=0.5) == "score_below_threshold"


def test_edge_rejection_reason_accepts_recovery_connectivity_cases_and_formats_counts():
    concept_doc_freq = {"energy grid": 10, "battery storage": 6}
    bridge_edge = {
        "hypernym": "energy grid",
        "hyponym": "battery storage",
        "score": 0.7,
        "evidence": {
            "method": "component_bridge",
            "semantic_similarity": 0.61,
            "similarity": 0.7,
            "lexical_similarity": 0.3,
        },
    }

    assert edge_rejection_reason(bridge_edge, concept_doc_freq, min_score=0.5, recovery_mode=True) is None
    assert connectivity_min_score(bridge_edge, 0.6, recovery_mode=True) <= 0.6
    assert format_reason_counts(Counter({"low_semantic_evidence": 2, "score_below_threshold": 1})) == "low_semantic_evidence=2, score_below_threshold=1"
