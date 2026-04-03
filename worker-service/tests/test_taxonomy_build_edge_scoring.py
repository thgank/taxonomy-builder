from app.pipeline.taxonomy_build.edge_scoring import (
    adaptive_bridge_budget,
    adaptive_method_thresholds,
    blend_scores,
    edge_method,
    edge_min_score,
    percentile,
    threshold_from_profile,
)


def test_percentile_and_edge_method_cover_multiple_shapes():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([], 50) == 0.0
    assert edge_method({"evidence": {"method": "hearst"}}) == "hearst"
    assert edge_method({"evidence": [{"method": "embedding_clustering"}]}) == "embedding_clustering"
    assert edge_method({"evidence": []}) == "unknown"


def test_adaptive_method_thresholds_uses_percentile_for_large_groups():
    pairs = [
        {"score": 0.91, "evidence": {"method": "hearst"}},
        {"score": 0.82, "evidence": {"method": "hearst"}},
        {"score": 0.79, "evidence": {"method": "hearst"}},
        {"score": 0.75, "evidence": {"method": "hearst"}},
        {"score": 0.5, "evidence": {"method": "component_bridge"}},
    ]

    thresholds = adaptive_method_thresholds(pairs, base_min_score=0.8, percentile_value=50)

    assert thresholds["hearst"] >= 0.75
    assert thresholds["component_bridge"] == 0.8


def test_edge_min_score_threshold_from_profile_and_blend_scores_work_together():
    profile = {
        "lang_method_thresholds": {"en": {"hearst": 0.73}},
        "method_thresholds": {"component_bridge": 0.61},
        "min_edge_accept_score": 0.58,
    }
    hearst_edge = {"evidence": {"method": "hearst"}}
    bridge_edge = {"evidence": {"method": "component_bridge"}}

    assert threshold_from_profile(profile, "hearst", "en", 0.55) == 0.73
    assert threshold_from_profile(profile, "component_bridge", "ru", 0.55) == 0.61
    assert edge_min_score(hearst_edge, 0.55, {"hearst": 0.72}) == 0.72
    assert edge_min_score(bridge_edge, 0.65, {}) == 0.56
    assert round(blend_scores(0.6, ranker_score=0.8, evidence_score=0.9), 3) == 0.722


def test_adaptive_bridge_budget_scales_with_gap_and_bounds():
    assert adaptive_bridge_budget(5, concept_count=20, current_lcr=0.9, target_lcr=0.9) >= 5
    assert adaptive_bridge_budget(5, concept_count=20, current_lcr=0.3, target_lcr=0.9) > 5
