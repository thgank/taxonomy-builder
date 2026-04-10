from types import SimpleNamespace
import uuid

from app.pipeline.taxonomy_build import edge_selector


def _concept(label, lang="en"):
    return SimpleNamespace(id=uuid.uuid4(), canonical=label, lang=lang)


def _ctx(**settings_overrides):
    concepts = [
        _concept("energy systems", "en"),
        _concept("battery storage", "en"),
        _concept("finance platform", "en"),
        _concept("credit market", "en"),
    ]
    concept_map = {concept.canonical: concept for concept in concepts}
    settings = SimpleNamespace(
        selector_include_rejected_candidates=False,
        selector_max_edges_factor=1.0,
        selector_parent_cap=2,
        selector_score_floor=0.6,
        selector_min_bridge_score=0.55,
        target_largest_component_ratio=0.9,
        selector_connectivity_bonus=0.08,
        selector_orphan_bonus=0.05,
        hubness_protected_max_per_parent=1,
        max_children_per_parent=3,
    )
    for key, value in settings_overrides.items():
        setattr(settings, key, value)
    return SimpleNamespace(
        settings=settings,
        concept_map=concept_map,
        concept_doc_freq={
            "energy systems": 9,
            "battery storage": 6,
            "finance platform": 8,
            "credit market": 4,
        },
        concept_labels=list(concept_map.keys()),
        dominant_lang="en",
        taxonomy_version_id="tax-1",
        collection_id="col-1",
    )


def _state():
    return SimpleNamespace(
        unique_pairs=[
            {"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.82, "evidence": {"method": "seed"}}
        ],
        candidate_logs=[
            {
                "parent_label": "energy systems",
                "child_label": "finance platform",
                "stage": "candidate_generation",
                "decision": "accepted",
                "method": "component_bridge",
                "final_score": 0.76,
                "feature_vector": {"semantic_similarity": 0.8},
                "evidence": {"method": "component_bridge"},
            },
            {
                "parent_label": "finance platform",
                "child_label": "credit market",
                "stage": "candidate_generation",
                "decision": "rejected",
                "method": "hearst",
                "final_score": 0.58,
                "feature_vector": {"semantic_similarity": 0.4},
                "evidence": {"method": "hearst"},
            },
        ],
        selector_stats=None,
    )


def test_helper_functions_cover_inference_cycles_and_adjustments():
    ctx = _ctx()
    adjacency = {"energy systems": {"battery storage"}, "battery storage": {"finance platform"}}

    assert edge_selector._infer_lang(ctx, "energy systems", "missing child") == "en"
    assert edge_selector._would_create_cycle(adjacency, "finance platform", "energy systems") is True
    assert edge_selector._would_create_cycle(adjacency, "energy systems", "credit market") is False
    assert edge_selector._method_adjustment("hearst") == 0.03
    assert edge_selector._method_adjustment("component_anchor_bridge") == -0.02
    assert edge_selector._method_adjustment("other") == 0.0


def test_collect_candidate_pool_merges_sources_and_optionally_includes_rejected():
    state = _state()

    pool = edge_selector._collect_candidate_pool(_ctx(), state)
    rejected_pool = edge_selector._collect_candidate_pool(_ctx(selector_include_rejected_candidates=True), state)

    assert len(pool) == 2
    assert len(rejected_pool) == 3
    merged = next(item for item in pool if item["edge"]["hyponym"] == "finance platform")
    assert merged["source_set"] == ["candidate_generation"]
    assert merged["decisions"] == ["accepted"]
    assert merged["feature_vector"]["semantic_similarity"] == 0.8


def test_collect_candidate_pool_skips_invalid_rows_and_updates_existing_payload():
    ctx = _ctx(selector_include_rejected_candidates=True)
    state = SimpleNamespace(
        unique_pairs=[
            {"hypernym": "", "hyponym": "battery storage", "score": 0.8, "evidence": {"method": "seed"}},
            {"hypernym": "energy systems", "hyponym": "missing concept", "score": 0.8, "evidence": {"method": "seed"}},
            {"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.0, "evidence": {"method": "seed"}},
            {"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.51, "evidence": []},
        ],
        candidate_logs=[
            {
                "parent_label": "energy systems",
                "child_label": "battery storage",
                "stage": "stage-a",
                "decision": "accepted",
                "method": "hearst",
                "final_score": 0.40,
                "feature_vector": {"semantic_similarity": 0.5},
                "evidence": [{"method": "hearst"}],
            },
            {
                "parent_label": "energy systems",
                "child_label": "battery storage",
                "stage": "stage-b",
                "decision": "accepted",
                "method": "component_bridge",
                "final_score": 0.81,
                "feature_vector": {"semantic_similarity": 0.9},
                "evidence": "not-a-dict",
            },
            {
                "parent_label": "",
                "child_label": "battery storage",
                "stage": "stage-c",
                "decision": "rejected",
                "method": "hearst",
                "final_score": 0.7,
                "feature_vector": {},
                "evidence": {"method": "hearst"},
            },
        ],
        selector_stats=None,
    )

    pool = edge_selector._collect_candidate_pool(ctx, state)

    assert len(pool) == 1
    item = pool[0]
    assert item["edge"]["score"] == 0.81
    assert item["edge"]["evidence"]["method"] == "component_bridge"
    assert item["source_set"] == ["preselector_graph", "stage-a", "stage-b"]
    assert item["feature_vector"]["semantic_similarity"] == 0.9


def test_select_edges_prioritizes_quality_then_connectivity(monkeypatch):
    ctx = _ctx()
    pool = [
        {
            "edge": {"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.90, "evidence": {"method": "hearst"}},
            "method": "hearst",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "finance platform", "hyponym": "credit market", "score": 0.88, "evidence": {"method": "hearst"}},
            "method": "hearst",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "energy systems", "hyponym": "finance platform", "score": 0.76, "evidence": {"method": "component_bridge"}},
            "method": "component_bridge",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "battery storage", "hyponym": "energy systems", "score": 0.77, "evidence": {"method": "component_bridge"}},
            "method": "component_bridge",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "energy systems", "hyponym": "credit market", "score": 0.40, "evidence": {"method": "hearst"}},
            "method": "hearst",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
    ]

    monkeypatch.setattr(edge_selector, "parent_validity_score", lambda _label, _freq: 0.9)
    monkeypatch.setattr(edge_selector, "is_low_quality_label", lambda _label: False)
    monkeypatch.setattr(edge_selector, "dedupe_pairs", lambda pairs: pairs)
    monkeypatch.setattr(edge_selector, "remove_cycles", lambda pairs: pairs)
    monkeypatch.setattr(edge_selector, "connectivity_critical_edge_keys", lambda *_args, **_kwargs: set())
    monkeypatch.setattr(edge_selector, "cap_protected_edge_keys_by_parent", lambda _pairs, protected, _freq, max_per_parent=1: protected)
    monkeypatch.setattr(edge_selector, "limit_parent_hubness", lambda pairs, _freq, max_children_per_parent=3, protected_edge_keys=None: pairs)
    monkeypatch.setattr(edge_selector, "collapse_bidirectional_pairs", lambda pairs, _freq: pairs)

    selected, stats = edge_selector._select_edges(ctx, pool)

    keys = {(edge["hypernym"], edge["hyponym"]) for edge in selected}
    assert ("energy systems", "battery storage") in keys
    assert ("finance platform", "credit market") in keys
    assert ("energy systems", "finance platform") in keys
    assert ("battery storage", "energy systems") not in keys
    assert stats["final_lcr"] == 1.0
    assert stats["method_mix"]["hearst"] == 2


def test_select_edges_second_pass_applies_connectivity_filters(monkeypatch):
    ctx = _ctx(
        selector_score_floor=0.8,
        selector_min_bridge_score=0.55,
        target_largest_component_ratio=0.6,
    )
    ctx.concept_labels = [
        "energy systems",
        "battery storage",
        "finance platform",
        "credit market",
        "weak parent",
        "low quality node",
        "isolated node",
    ]
    pool = [
        {
            "edge": {"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.90, "evidence": {"method": "hearst"}},
            "method": "hearst",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "finance platform", "hyponym": "credit market", "score": 0.88, "evidence": {"method": "hearst"}},
            "method": "hearst",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "energy systems", "hyponym": "finance platform", "score": 0.76, "evidence": {"method": "component_bridge"}},
            "method": "component_bridge",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "energy systems", "hyponym": "weak parent", "score": 0.50, "evidence": {"method": "component_bridge"}},
            "method": "component_bridge",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "energy systems", "hyponym": "low quality node", "score": 0.70, "evidence": {"method": "component_bridge"}},
            "method": "component_bridge",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "weak parent", "hyponym": "finance platform", "score": 0.72, "evidence": {"method": "component_bridge"}},
            "method": "component_bridge",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "weak parent", "hyponym": "isolated node", "score": 0.78, "evidence": {"method": "component_bridge"}},
            "method": "component_bridge",
            "decisions": ["accepted"],
            "feature_vector": {},
        },
        {
            "edge": {"hypernym": "battery storage", "hyponym": "energy systems", "score": 0.79, "evidence": {"method": "component_bridge"}},
            "method": "component_bridge",
            "decisions": ["rejected"],
            "feature_vector": {},
        },
    ]

    original_component_index = edge_selector._component_index
    call_counter = {"count": 0}

    def staged_component_index(edges, nodes):
        call_counter["count"] += 1
        if call_counter["count"] <= 3:
            return {node: 0 for node in nodes}, {0: set(nodes)}
        return original_component_index(edges, nodes)

    monkeypatch.setattr(edge_selector, "_component_index", staged_component_index)
    monkeypatch.setattr(edge_selector, "parent_validity_score", lambda label, _freq: 0.2 if label == "weak parent" else 0.9)
    monkeypatch.setattr(edge_selector, "is_low_quality_label", lambda label: label == "low quality node")
    monkeypatch.setattr(edge_selector, "dedupe_pairs", lambda pairs: pairs)
    monkeypatch.setattr(edge_selector, "remove_cycles", lambda pairs: pairs)
    monkeypatch.setattr(edge_selector, "connectivity_critical_edge_keys", lambda *_args, **_kwargs: set())
    monkeypatch.setattr(edge_selector, "cap_protected_edge_keys_by_parent", lambda _pairs, protected, _freq, max_per_parent=1: protected)
    monkeypatch.setattr(edge_selector, "limit_parent_hubness", lambda pairs, _freq, max_children_per_parent=3, protected_edge_keys=None: pairs)
    monkeypatch.setattr(edge_selector, "collapse_bidirectional_pairs", lambda pairs, _freq: pairs)

    selected, stats = edge_selector._select_edges(ctx, pool)

    keys = {(edge["hypernym"], edge["hyponym"]) for edge in selected}
    assert ("energy systems", "finance platform") in keys
    assert ("energy systems", "weak parent") not in keys
    assert ("weak parent", "finance platform") not in keys
    assert ("energy systems", "low quality node") not in keys
    assert ("battery storage", "energy systems") not in keys
    assert stats["final_lcr"] >= 0.57


def test_selector_logs_and_apply_global_edge_selector_cover_success_and_fallback(monkeypatch):
    ctx = _ctx()
    state = _state()
    selected = [{"hypernym": "energy systems", "hyponym": "finance platform", "score": 0.76, "evidence": {"method": "component_bridge"}}]
    pool = edge_selector._collect_candidate_pool(_ctx(selector_include_rejected_candidates=True), state)

    logs = edge_selector._selector_logs(
        _ctx(selector_include_rejected_candidates=True),
        pool,
        selected_keys={("energy systems", "finance platform")},
        score_floor=0.6,
    )
    accepted_log = next(log for log in logs if log["child_label"] == "finance platform")
    rejected_log = next(log for log in logs if log["child_label"] == "credit market")
    assert accepted_log["decision"] == "accepted"
    assert rejected_log["rejection_reason"] in {"selector_not_chosen", "selector_score_below_floor"}

    monkeypatch.setattr(edge_selector, "_collect_candidate_pool", lambda _ctx, _state: pool)
    monkeypatch.setattr(
        edge_selector,
        "_select_edges",
        lambda _ctx, _pool: (
            selected,
            {"pool_size": len(pool), "selected": 1, "final_lcr": 1.0, "method_mix": {"component_bridge": 1}},
        ),
    )

    stats = edge_selector.apply_global_edge_selector(ctx, state)

    assert stats["fallback"] is False
    assert state.unique_pairs == selected
    assert len(state.candidate_logs) >= 2

    fallback_state = _state()
    monkeypatch.setattr(edge_selector, "_collect_candidate_pool", lambda _ctx, _state: pool)
    monkeypatch.setattr(edge_selector, "_select_edges", lambda _ctx, _pool: ([], {"pool_size": len(pool)}))
    fallback_stats = edge_selector.apply_global_edge_selector(ctx, fallback_state)
    assert fallback_stats["fallback"] is True

    empty_state = _state()
    monkeypatch.setattr(edge_selector, "_collect_candidate_pool", lambda _ctx, _state: [])
    empty_stats = edge_selector.apply_global_edge_selector(ctx, empty_state)
    assert empty_stats["pool_size"] == 0
