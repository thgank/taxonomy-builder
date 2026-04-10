from types import SimpleNamespace

from app.pipeline.taxonomy_build import build_recovery_quality


def _ctx(**settings_overrides):
    settings = SimpleNamespace(
        adaptive_target_lcr_enabled=True,
        target_largest_component_ratio=0.7,
        adaptive_target_lcr_min_components=3,
        adaptive_target_lcr_gap_trigger=0.05,
        adaptive_target_lcr_min_coverage=0.35,
        adaptive_target_lcr_value=0.9,
        adaptive_target_component_ratio=0.2,
        adaptive_target_component_min_count=1,
        root_consolidation_enabled=True,
        root_consolidation_max_links=2,
        root_consolidation_max_root_outdegree=3,
        root_consolidation_min_similarity=0.1,
        orientation_sanity_enabled=True,
        orientation_sanity_low_score_threshold=0.6,
        orientation_sanity_max_rewrites=2,
        connectivity_repair_enabled=True,
        lcr_recovery_mode_enabled=True,
        lcr_recovery_margin=0.1,
        connectivity_repair_max_links=3,
        coverage_recovery_enabled=True,
        coverage_recovery_target=0.9,
        orphan_link_threshold=0.6,
        coverage_recovery_max_links=4,
        evidence_linking_enabled=False,
        evidence_top_k=2,
        max_children_per_parent=3,
        hubness_protected_max_per_parent=1,
        quality_thresholds={"max_hubness": 2},
    )
    for key, value in settings_overrides.items():
        setattr(settings, key, value)
    return SimpleNamespace(
        session=SimpleNamespace(),
        job_id="job-1",
        collection_id="col-1",
        taxonomy_version_id="tax-1",
        settings=settings,
        concepts=[
            SimpleNamespace(canonical="energy systems"),
            SimpleNamespace(canonical="battery energy systems"),
            SimpleNamespace(canonical="battery storage"),
            SimpleNamespace(canonical="grid support"),
        ],
        concept_labels=[
            "energy systems",
            "battery energy systems",
            "battery storage",
            "grid support",
        ],
        concept_doc_freq={
            "energy systems": 9,
            "battery energy systems": 8,
            "battery storage": 5,
            "grid support": 4,
        },
        concept_scores={
            "energy systems": 0.9,
            "battery energy systems": 0.8,
            "battery storage": 0.7,
            "grid support": 0.6,
        },
        evidence_index={},
    )


def _state(unique_pairs=None):
    return SimpleNamespace(
        unique_pairs=list(unique_pairs or []),
        connectivity_candidate_pool=[],
        min_edge_accept_score=0.5,
        method_thresholds={
            "component_bridge": 0.5,
            "component_anchor_bridge": 0.5,
            "connectivity_repair_fallback": 0.5,
            "orientation_sanity_rewrite": 0.5,
            "root_consolidation": 0.5,
            "orphan_safe_link": 0.5,
        },
        candidate_logs=[],
    )


def test_helper_functions_compute_targets_and_similarity(monkeypatch):
    ctx = _ctx()
    state = _state(
        [
            {"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.8},
            {"hypernym": "battery energy systems", "hyponym": "grid support", "score": 0.7},
        ]
    )
    monkeypatch.setattr(build_recovery_quality, "coverage_from_pairs", lambda _pairs, _labels: 0.55)
    monkeypatch.setattr(
        build_recovery_quality,
        "components_with_nodes",
        lambda _pairs, _labels: [{"energy systems", "battery storage"}, {"battery energy systems"}, {"grid support"}],
    )

    effective, info = build_recovery_quality._effective_target_lcr(ctx, state, post_hub_lcr=0.5)

    assert effective == 0.9
    assert info["severe_fragmentation"] is True
    assert build_recovery_quality._target_component_count(ctx, component_count=6) == 1
    assert build_recovery_quality._lexical_similarity("battery energy systems", "energy systems") > 0.3
    assert build_recovery_quality._max_parent_outdegree(state.unique_pairs) == 1


def test_run_root_consolidation_adds_parent_link_and_logs(monkeypatch):
    ctx = _ctx()
    state = _state(
        [
            {"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.82, "evidence": {"method": "seed"}},
            {"hypernym": "battery energy systems", "hyponym": "grid support", "score": 0.78, "evidence": {"method": "seed"}},
        ]
    )
    events = []

    monkeypatch.setattr(build_recovery_quality, "parent_validity_score", lambda _label, _freq: 0.9)
    monkeypatch.setattr(build_recovery_quality, "connectivity_min_score", lambda edge, _min_score, recovery_mode=False: edge["score"] - 0.1)
    monkeypatch.setattr(build_recovery_quality, "edge_min_score", lambda *_args, **_kwargs: 0.5)
    monkeypatch.setattr(build_recovery_quality, "edge_rejection_reason", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(build_recovery_quality, "dedupe_pairs", lambda pairs: pairs)
    monkeypatch.setattr(build_recovery_quality, "collapse_bidirectional_pairs", lambda pairs, _freq: pairs)
    monkeypatch.setattr(build_recovery_quality, "remove_cycles", lambda pairs: pairs)
    monkeypatch.setattr(build_recovery_quality, "add_job_event", lambda _session, _job_id, _level, message: events.append(message))

    build_recovery_quality._run_root_consolidation(ctx, state)

    keys = {(edge["hypernym"], edge["hyponym"]) for edge in state.unique_pairs}
    assert ("energy systems", "battery energy systems") in keys or ("battery energy systems", "energy systems") in keys
    assert any("Root consolidation added 1/2 edges" in message for message in events)


def test_run_orientation_sanity_rewrites_suspicious_edge(monkeypatch):
    ctx = _ctx()
    state = _state(
        [
            {
                "hypernym": "battery storage systems",
                "hyponym": "energy systems",
                "score": 0.4,
                "evidence": {"method": "component_bridge"},
            }
        ]
    )
    events = []

    monkeypatch.setattr(
        build_recovery_quality,
        "parent_validity_score",
        lambda label, _freq: 0.4 if label == "battery storage systems" else 0.9,
    )
    monkeypatch.setattr(build_recovery_quality, "edge_min_score", lambda *_args, **_kwargs: 0.5)
    monkeypatch.setattr(build_recovery_quality, "edge_rejection_reason", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(build_recovery_quality, "dedupe_pairs", lambda pairs: pairs)
    monkeypatch.setattr(build_recovery_quality, "collapse_bidirectional_pairs", lambda pairs, _freq: pairs)
    monkeypatch.setattr(build_recovery_quality, "remove_cycles", lambda pairs: pairs)
    monkeypatch.setattr(build_recovery_quality, "add_job_event", lambda _session, _job_id, _level, message: events.append(message))

    build_recovery_quality._run_orientation_sanity(ctx, state)

    assert state.unique_pairs[0]["hypernym"] == "energy systems"
    assert state.unique_pairs[0]["hyponym"] == "battery storage systems"
    assert state.unique_pairs[0]["evidence"]["method"] == "orientation_sanity_rewrite"
    assert any("Orientation sanity rewrote 1 edges" in message for message in events)


def test_run_connectivity_repair_generates_candidates_repairs_and_logs(monkeypatch):
    ctx = _ctx()
    state = _state([{"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.8, "evidence": {"method": "seed"}}])
    events = []

    monkeypatch.setattr(
        build_recovery_quality,
        "_effective_target_lcr",
        lambda _ctx, _state, _post_hub_lcr: (
            0.9,
            {
                "adaptive_enabled": True,
                "coverage": 0.4,
                "component_count": 3,
                "base_target": 0.7,
                "effective_target": 0.9,
            },
        ),
    )
    monkeypatch.setattr(build_recovery_quality, "_target_component_count", lambda _ctx, _count: 1)
    monkeypatch.setattr(
        build_recovery_quality,
        "fallback_connectivity_candidates",
        lambda *_args, **_kwargs: [{"hypernym": "energy systems", "hyponym": "grid support", "score": 0.7, "evidence": {"method": "connectivity_repair_fallback"}}],
    )
    monkeypatch.setattr(
        build_recovery_quality,
        "fallback_semantic_connectivity_candidates",
        lambda *_args, **_kwargs: [{"hypernym": "battery energy systems", "hyponym": "grid support", "score": 0.74, "evidence": {"method": "connectivity_repair_fallback"}}],
    )
    monkeypatch.setattr(
        build_recovery_quality,
        "repair_connectivity",
        lambda **_kwargs: (
            [{"hypernym": "battery energy systems", "hyponym": "grid support", "score": 0.74, "evidence": {"method": "connectivity_repair_fallback"}}],
            {
                "selected": 1,
                "candidate_pairs_unique": 3,
                "considered": 2,
                "skipped_existing": 0,
                "skipped_same_component": 0,
                "skipped_low_parent_validity": 0,
                "skipped_low_quality_label": 0,
                "skipped_low_score": 0,
                "initial_component_count": 3,
                "final_component_count": 1,
                "target_component_count": 1,
            },
        ),
    )
    monkeypatch.setattr(build_recovery_quality, "dedupe_pairs", lambda pairs: pairs)
    monkeypatch.setattr(build_recovery_quality, "collapse_bidirectional_pairs", lambda pairs, _freq: pairs)
    monkeypatch.setattr(build_recovery_quality, "largest_component_ratio_from_pairs", lambda _pairs, _labels: 0.95)
    monkeypatch.setattr(build_recovery_quality, "add_job_event", lambda _session, _job_id, _level, message: events.append(message))

    build_recovery_quality._run_connectivity_repair(
        ctx,
        state,
        pre_prune_pairs=list(state.unique_pairs),
        post_hub_lcr=0.4,
    )

    assert len(state.connectivity_candidate_pool) == 2
    assert any(edge["hyponym"] == "grid support" for edge in state.unique_pairs)
    assert any("Connectivity repair target" in message for message in events)
    assert any("Connectivity repair added 1 edges" in message for message in events)


def test_run_coverage_recovery_uses_second_pass_and_logs(monkeypatch):
    ctx = _ctx()
    state = _state([{"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.8, "evidence": {"method": "seed"}}])
    events = []
    coverage_values = iter([0.2, 0.45, 0.95])
    orphan_batches = iter(
        [
            [{"hypernym": "energy systems", "hyponym": "grid support", "score": 0.66, "evidence": {"method": "orphan_safe_link"}}],
            [{"hypernym": "battery energy systems", "hyponym": "grid support", "score": 0.62, "evidence": {"method": "orphan_safe_link"}}],
        ]
    )

    monkeypatch.setattr(build_recovery_quality, "coverage_from_pairs", lambda _pairs, _labels: next(coverage_values))
    monkeypatch.setattr(build_recovery_quality, "safe_link_orphans", lambda *_args, **_kwargs: next(orphan_batches))
    monkeypatch.setattr(build_recovery_quality, "connectivity_min_score", lambda edge, _min_score, recovery_mode=False: edge["score"] - 0.1)
    monkeypatch.setattr(build_recovery_quality, "edge_min_score", lambda *_args, **_kwargs: 0.5)
    monkeypatch.setattr(build_recovery_quality, "edge_rejection_reason", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(build_recovery_quality, "dedupe_pairs", lambda pairs: pairs)
    monkeypatch.setattr(build_recovery_quality, "collapse_bidirectional_pairs", lambda pairs, _freq: pairs)
    monkeypatch.setattr(build_recovery_quality, "add_job_event", lambda _session, _job_id, _level, message: events.append(message))

    build_recovery_quality._run_coverage_recovery(ctx, state)

    assert len(state.unique_pairs) == 3
    assert any("Coverage recovery added 2/2 edges" in message for message in events)
