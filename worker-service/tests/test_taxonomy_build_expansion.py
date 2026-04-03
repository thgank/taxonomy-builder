from types import SimpleNamespace

from app.pipeline.taxonomy_build import build_expansion


def _ctx(**settings_overrides):
    settings = SimpleNamespace(
        adaptive_thresholds_enabled=False,
        edge_ranker_min_confidence=0.7,
        evidence_linking_enabled=True,
        edge_ranker_blend_alpha=0.5,
        global_selector_enabled=True,
        orphan_linking_enabled=True,
        orphan_link_threshold=0.6,
        orphan_link_max_links=4,
        evidence_top_k=2,
        component_bridging_enabled=True,
        target_largest_component_ratio=0.7,
        lcr_recovery_mode_enabled=True,
        lcr_recovery_margin=0.2,
        component_bridge_threshold=0.68,
        component_bridge_max_links=5,
        bridge_max_new_children_per_parent=1,
        bridge_parent_load_penalty_alpha=0.02,
        anchor_bridging_enabled=True,
        anchor_bridge_max_links=3,
    )
    for key, value in settings_overrides.items():
        setattr(settings, key, value)
    return SimpleNamespace(
        session=SimpleNamespace(),
        job_id="job-1",
        chunks=[],
        concepts=["a", "b", "c", "d"],
        concept_labels=["energy", "battery storage", "grid battery", "microgrid"],
        concept_doc_freq={"energy": 8, "battery storage": 5, "grid battery": 4, "microgrid": 3},
        concept_scores={"energy": 0.9, "battery storage": 0.8, "grid battery": 0.7, "microgrid": 0.65},
        threshold_profile={},
        evidence_index={},
        settings=settings,
    )


def _state():
    return SimpleNamespace(
        unique_pairs=[{"hypernym": "energy", "hyponym": "battery storage", "score": 0.8, "evidence": {"method": "seed"}}],
        connectivity_candidate_pool=[],
        candidate_logs=[],
        min_edge_accept_score=0.55,
        method_thresholds={"hearst": 0.55},
    )


def test_accept_new_edges_accepts_and_defers_soft_rejections(monkeypatch):
    ctx = _ctx()
    state = _state()
    new_edges = [
        {"hypernym": "energy", "hyponym": "grid battery", "score": 0.7, "evidence": {"method": "hearst"}},
        {"hypernym": "energy", "hyponym": "microgrid", "score": 0.4, "evidence": {"method": "hearst"}},
    ]

    monkeypatch.setattr(build_expansion, "compute_pair_cooccurrence", lambda _chunks, _labels: {})
    monkeypatch.setattr(build_expansion, "extract_edge_features", lambda *_args, **_kwargs: {"semantic_similarity": 0.8, "lexical_similarity": 0.3, "cooccurrence_support": 0.1, "parent_validity": 0.9, "method": "hearst", "lang": "en"})
    monkeypatch.setattr(build_expansion, "edge_min_score", lambda *_args, **_kwargs: 0.5)
    monkeypatch.setattr(build_expansion, "predict_ranker_score", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(build_expansion, "blend_scores", lambda **kwargs: kwargs["base_score"])
    monkeypatch.setattr(build_expansion, "build_candidate_log", lambda _ctx, edge, _features, decision, rejection_reason, **kwargs: {"edge": edge["hyponym"], "decision": decision, "reason": rejection_reason, "stage": kwargs["stage"]})

    def fake_reason(edge, _freq, _min_score, recovery_mode=False):
        return None if edge["hyponym"] == "grid battery" else "score_below_threshold"

    monkeypatch.setattr(build_expansion, "edge_rejection_reason", fake_reason)

    accepted = build_expansion._accept_new_edges(ctx, state, state.unique_pairs, new_edges, stage="orphan_linking")

    assert len(accepted) == 1
    assert accepted[0]["hyponym"] == "grid battery"
    assert len(state.connectivity_candidate_pool) == 1
    assert state.candidate_logs[0]["decision"] == "accepted"
    assert state.candidate_logs[1]["reason"] == "score_below_threshold"


def test_apply_connectivity_expansion_runs_orphan_passes_and_follow_up_bridges(monkeypatch):
    ctx = _ctx()
    state = _state()
    events = []
    run_calls = []
    orphan_batches = iter([
        [{"hypernym": "energy", "hyponym": "grid battery", "score": 0.71, "evidence": {"method": "orphan_safe_link"}}],
        [{"hypernym": "energy", "hyponym": "microgrid", "score": 0.69, "evidence": {"method": "orphan_safe_link"}}],
    ])

    monkeypatch.setattr(build_expansion, "safe_link_orphans", lambda *_args, **_kwargs: next(orphan_batches))
    monkeypatch.setattr(build_expansion, "_accept_new_edges", lambda _ctx, _state, _current, new_pairs, **_kwargs: new_pairs)
    monkeypatch.setattr(build_expansion, "compute_graph_quality", lambda pairs, _count: {"largest_component_ratio": 0.1 if len(pairs) == 2 else 0.4})
    monkeypatch.setattr(build_expansion, "_run_component_bridging", lambda *_args, **_kwargs: run_calls.append("component"))
    monkeypatch.setattr(build_expansion, "_run_anchor_bridging", lambda *_args, **_kwargs: run_calls.append("anchor"))
    monkeypatch.setattr(build_expansion, "add_job_event", lambda _session, _job_id, _level, message: events.append(message))

    build_expansion.apply_connectivity_expansion(ctx, state)

    assert len(state.unique_pairs) == 3
    assert run_calls == ["component", "anchor"]
    assert any("Orphan safe-linking added 1 edges" in message for message in events)
    assert any("second pass added 1 edges" in message for message in events)


def test_run_component_bridging_handles_skip_zero_accepts_and_success(monkeypatch):
    ctx = _ctx()
    state = _state()
    events = []
    qualities = iter([
        {"largest_component_ratio": 0.2},
        {"largest_component_ratio": 0.2},
        {"largest_component_ratio": 0.2},
        {"largest_component_ratio": 0.72},
    ])
    bridge_batches = iter([
        [{"hypernym": "energy", "hyponym": "grid battery", "score": 0.7, "evidence": {"method": "component_bridge"}}],
        [{"hypernym": "energy", "hyponym": "microgrid", "score": 0.72, "evidence": {"method": "component_bridge"}}],
    ])
    accepted_batches = iter([[], [{"hypernym": "energy", "hyponym": "microgrid", "score": 0.72, "evidence": {"method": "component_bridge"}}]])

    monkeypatch.setattr(build_expansion, "compute_graph_quality", lambda *_args, **_kwargs: next(qualities))
    monkeypatch.setattr(build_expansion, "adaptive_bridge_budget", lambda **_kwargs: 2)
    monkeypatch.setattr(build_expansion, "bridge_components", lambda *_args, **_kwargs: next(bridge_batches))
    monkeypatch.setattr(build_expansion, "_accept_new_edges", lambda *_args, **_kwargs: next(accepted_batches))
    monkeypatch.setattr(build_expansion, "add_job_event", lambda _session, _job_id, _level, message: events.append(message))

    build_expansion._run_component_bridging(ctx, state)

    assert any("accepted 0/1" in message for message in events)
    assert any("added 1/1 edges" in message for message in events)
    assert any(edge["hyponym"] == "microgrid" for edge in state.unique_pairs)


def test_run_anchor_bridging_applies_parent_cap_and_load_penalties(monkeypatch):
    ctx = _ctx()
    state = _state()
    events = []
    monkeypatch.setattr(build_expansion, "compute_graph_quality", lambda *_args, **_kwargs: {"largest_component_ratio": 0.25})
    monkeypatch.setattr(
        build_expansion,
        "anchor_connect_components",
        lambda *_args, **_kwargs: [
            {"hypernym": "energy", "hyponym": "grid battery", "score": 0.75, "evidence": {"method": "component_anchor_bridge"}},
            {"hypernym": "energy", "hyponym": "microgrid", "score": 0.74, "evidence": {"method": "component_anchor_bridge"}},
        ],
    )
    monkeypatch.setattr(build_expansion, "_accept_new_edges", lambda _ctx, _state, _current, adjusted_links, **_kwargs: adjusted_links[:1])
    monkeypatch.setattr(build_expansion, "add_job_event", lambda _session, _job_id, _level, message: events.append(message))

    build_expansion._run_anchor_bridging(ctx, state)

    assert len(state.unique_pairs) == 2
    assert len(state.connectivity_candidate_pool) == 2
    assert any("Anchor component bridging added 1/2 edges" in message for message in events)

