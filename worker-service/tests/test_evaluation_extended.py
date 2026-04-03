from types import SimpleNamespace
import uuid

from app.pipeline.evaluation import (
    _compute_cross_lang_consistency,
    _compute_fragmentation_and_risk_metrics,
    _compute_graph_connectivity_metrics,
    _compute_manual_review_metrics,
    _compute_quality_score_10,
)


def _concept(label: str, lang: str = "en"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        canonical=label,
        lang=lang,
    )


def _edge(parent_id, child_id, score=0.8, approved=None):
    return SimpleNamespace(
        parent_concept_id=parent_id,
        child_concept_id=child_id,
        score=score,
        approved=approved,
    )


def test_compute_graph_connectivity_metrics_reports_global_and_language_views():
    parent = _concept("energy systems", "en")
    child = _concept("battery storage", "en")
    orphan = _concept("grid balancing", "en")
    kk_parent = _concept("энергия жүйелері", "kk")
    kk_child = _concept("батарея сақтау", "kk")
    edges = [
        _edge(parent.id, child.id),
        _edge(kk_parent.id, kk_child.id),
    ]

    result = _compute_graph_connectivity_metrics(
        [parent, child, orphan, kk_parent, kk_child],
        edges,
        {str(parent.id), str(child.id), str(kk_parent.id), str(kk_child.id)},
    )

    assert result["all_concepts"]["denominator"] == 5
    assert result["all_concepts"]["largest_component_ratio"] > 0
    assert "en" in result["by_language"]
    assert result["by_language"]["kk"]["all_concepts"]["edge_count"] == 1


def test_compute_fragmentation_and_risk_metrics_detects_low_score_orientation_risk():
    parent = _concept("battery storage systems")
    child = _concept("battery storage")
    isolated = _concept("grid markets")
    edges = [_edge(parent.id, child.id, score=0.4)]
    concept_doc_sets = {
        str(parent.id): {"d1"},
        str(child.id): {"d1", "d2", "d3"},
    }

    result = _compute_fragmentation_and_risk_metrics(
        [parent, child, isolated],
        edges,
        concept_doc_sets,
    )

    assert result["component_count"] == 2
    assert result["low_score_edge_count"] == 1
    assert result["orientation_risk_count"] == 1
    assert result["orientation_risk_examples"][0]["child"] == "battery storage"


def test_compute_manual_review_metrics_counts_approvals_and_rejections():
    edges = [
        _edge(uuid.uuid4(), uuid.uuid4(), approved=True),
        _edge(uuid.uuid4(), uuid.uuid4(), approved=False),
        _edge(uuid.uuid4(), uuid.uuid4(), approved=None),
    ]

    result = _compute_manual_review_metrics(edges)

    assert result["reviewed_edges"] == 2
    assert result["approved_edges"] == 1
    assert result["rejected_edges"] == 1
    assert result["manual_disagreement_rate"] == 0.5


def test_compute_cross_lang_consistency_flags_reverse_pairs_across_languages():
    en_parent = _concept("energy system", "en")
    en_child = _concept("battery storage", "en")
    ru_parent = _concept("battery storage", "ru")
    ru_child = _concept("energy system", "ru")
    edges = [
        _edge(en_parent.id, en_child.id),
        _edge(ru_parent.id, ru_child.id),
    ]

    result = _compute_cross_lang_consistency(
        [en_parent, en_child, ru_parent, ru_child],
        edges,
    )

    assert result["comparable_pairs"] == 2
    assert result["consistent_pairs"] == 0
    assert result["cross_lang_consistency"] == 0.0
    assert len(result["sample_conflicts"]) >= 1


def test_compute_quality_score_10_combines_positive_and_negative_signals():
    score = _compute_quality_score_10(
        structural={"coverage_candidate_set": 0.9},
        graph_connectivity={"all_concepts": {"largest_component_ratio": 0.85, "hubness": 1.5}},
        risk={"fragmentation_index": 0.15, "low_score_edge_ratio": 0.1},
        manual_review={"manual_disagreement_rate": 0.05},
    )

    assert 0 < score <= 10
    assert score > 7
