from __future__ import annotations

from collections import Counter, defaultdict

from app.pipeline.taxonomy_build.build_types import BuildContext, BuildState
from app.pipeline.taxonomy_build.edge_filters import parent_validity_score
from app.pipeline.taxonomy_build.edge_scoring import edge_method
from app.pipeline.taxonomy_build.graph_metrics import (
    components_with_nodes,
    dedupe_pairs,
    edge_key,
    largest_component_ratio_from_pairs,
)
from app.pipeline.taxonomy_build.pair_ops import (
    cap_protected_edge_keys_by_parent,
    collapse_bidirectional_pairs,
    connectivity_critical_edge_keys,
    limit_parent_hubness,
)
from app.pipeline.taxonomy_quality import remove_cycles
from app.pipeline.taxonomy_text import is_low_quality_label


def _infer_lang(ctx: BuildContext, parent_label: str, child_label: str) -> str:
    parent = ctx.concept_map.get(parent_label)
    child = ctx.concept_map.get(child_label)
    lang = (parent.lang if parent else None) or (child.lang if child else None) or ctx.dominant_lang or "en"
    return (lang or "en").lower()[:2]


def _would_create_cycle(adjacency: dict[str, set[str]], parent: str, child: str) -> bool:
    if parent == child:
        return True
    stack = [child]
    visited: set[str] = set()
    while stack:
        node = stack.pop()
        if node == parent:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, set()) - visited)
    return False


def _component_index(edges: list[dict], nodes: list[str]) -> tuple[dict[str, int], dict[int, set[str]]]:
    comps = components_with_nodes(edges, nodes)
    idx: dict[str, int] = {}
    comp_map: dict[int, set[str]] = {}
    for i, comp in enumerate(comps):
        comp_map[i] = set(comp)
        for n in comp:
            idx[n] = i
    return idx, comp_map


def _method_adjustment(method: str) -> float:
    m = (method or "").lower()
    if m in {"embedding_clustering", "hearst", "hearst_trigger_fallback"}:
        return 0.03
    if m in {"component_bridge", "orphan_safe_link"}:
        return 0.01
    if m in {"component_anchor_bridge", "connectivity_repair_fallback", "hubness_rebalance_reattach"}:
        return -0.02
    return 0.0


def _collect_candidate_pool(ctx: BuildContext, state: BuildState) -> list[dict]:
    include_rejected = bool(ctx.settings.selector_include_rejected_candidates)
    by_key: dict[tuple[str, str], dict] = {}

    def upsert(
        edge: dict,
        source: str,
        decision: str | None = None,
        feature_vector: dict | None = None,
        explicit_method: str | None = None,
    ) -> None:
        parent = str(edge.get("hypernym", "") or "").strip()
        child = str(edge.get("hyponym", "") or "").strip()
        if not parent or not child:
            return
        if parent not in ctx.concept_map or child not in ctx.concept_map:
            return
        score = float(edge.get("score", 0.0) or 0.0)
        if score <= 0.0:
            return
        key = (parent, child)
        ev = edge.get("evidence", {})
        if isinstance(ev, list):
            ev = ev[0] if ev and isinstance(ev[0], dict) else {}
        if not isinstance(ev, dict):
            ev = {}
        method = explicit_method or str(ev.get("method") or edge_method(edge) or "unknown")
        if "method" not in ev:
            ev["method"] = method
        row = by_key.get(key)
        payload = {
            "edge": {
                "hypernym": parent,
                "hyponym": child,
                "score": round(score, 4),
                "evidence": ev,
            },
            "method": method,
            "max_score": score,
            "source_set": {source},
            "decisions": {decision} if decision else set(),
            "feature_vector": dict(feature_vector or {}),
        }
        if row is None:
            by_key[key] = payload
            return
        row["source_set"].add(source)
        if decision:
            row["decisions"].add(decision)
        if score > float(row.get("max_score", 0.0) or 0.0):
            row["edge"] = payload["edge"]
            row["max_score"] = score
            row["method"] = method
            if feature_vector:
                row["feature_vector"] = dict(feature_vector)
        elif feature_vector and not row.get("feature_vector"):
            row["feature_vector"] = dict(feature_vector)

    for edge in state.unique_pairs:
        upsert(edge, source="preselector_graph", decision="accepted")

    for log in state.candidate_logs:
        decision = str(log.get("decision", "pending"))
        if (not include_rejected) and decision == "rejected":
            continue
        parent = str(log.get("parent_label", "") or "").strip()
        child = str(log.get("child_label", "") or "").strip()
        if not parent or not child:
            continue
        evidence = log.get("evidence", {})
        if isinstance(evidence, list):
            evidence = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
        if not isinstance(evidence, dict):
            evidence = {}
        method = str(log.get("method") or evidence.get("method") or "unknown")
        if "method" not in evidence:
            evidence["method"] = method
        score = float(log.get("final_score", log.get("base_score", 0.0)) or 0.0)
        edge = {
            "hypernym": parent,
            "hyponym": child,
            "score": round(score, 4),
            "evidence": evidence,
        }
        upsert(
            edge,
            source=str(log.get("stage", "candidate_log")),
            decision=decision,
            feature_vector=dict(log.get("feature_vector") or {}),
            explicit_method=method,
        )

    out = []
    for item in by_key.values():
        item["source_set"] = sorted(item["source_set"])
        item["decisions"] = sorted(item["decisions"])
        out.append(item)
    return out


def _select_edges(ctx: BuildContext, pool: list[dict]) -> tuple[list[dict], dict]:
    if not pool:
        return [], {"pool_size": 0, "selected": 0}
    concept_count = max(1, len(ctx.concept_labels))
    max_edges = int(max(8, round(concept_count * max(0.2, min(1.5, ctx.settings.selector_max_edges_factor)))))
    max_edges = min(max_edges, len(pool))
    parent_cap = max(2, int(ctx.settings.selector_parent_cap))
    score_floor = float(ctx.settings.selector_score_floor)
    bridge_floor = float(min(score_floor, ctx.settings.selector_min_bridge_score))
    target_lcr = float(ctx.settings.target_largest_component_ratio)
    method_adjust = {item["method"]: _method_adjustment(item["method"]) for item in pool}

    selected: list[dict] = []
    selected_keys: set[tuple[str, str]] = set()
    out_degree: Counter[str] = Counter()
    degree: Counter[str] = Counter()
    adjacency: dict[str, set[str]] = defaultdict(set)

    def add_edge(edge: dict) -> None:
        selected.append(edge)
        key = edge_key(edge)
        selected_keys.add(key)
        p, c = key
        out_degree[p] += 1
        degree[p] += 1
        degree[c] += 1
        adjacency[p].add(c)

    # Pass 1: quality-first with connectivity-aware utility.
    while len(selected) < max_edges:
        comp_idx, _comp_map = _component_index(selected, ctx.concept_labels)
        best = None
        best_u = -10.0
        for item in pool:
            edge = item["edge"]
            key = edge_key(edge)
            if key in selected_keys:
                continue
            parent = edge["hypernym"]
            child = edge["hyponym"]
            score = float(edge.get("score", 0.0) or 0.0)
            if score <= 0.0:
                continue
            if is_low_quality_label(parent) or is_low_quality_label(child):
                continue
            if parent_validity_score(parent, ctx.concept_doc_freq) < 0.40:
                continue
            cross_component = comp_idx.get(parent, -1) != comp_idx.get(child, -1)
            floor = bridge_floor if cross_component else score_floor
            if score < floor:
                continue
            if out_degree[parent] >= parent_cap and not cross_component:
                continue
            if _would_create_cycle(adjacency, parent, child):
                continue
            utility = score
            utility += method_adjust.get(item["method"], 0.0)
            if cross_component:
                utility += float(ctx.settings.selector_connectivity_bonus)
            if degree[parent] == 0 or degree[child] == 0:
                utility += float(ctx.settings.selector_orphan_bonus)
            utility -= 0.02 * max(0, out_degree[parent] - parent_cap + 1)
            if "rejected" in item.get("decisions", []):
                utility -= 0.01
            if utility > best_u:
                best = edge
                best_u = utility
        if best is None:
            break
        add_edge(best)

    # Pass 2: explicit connectivity lift if LCR is still below target.
    while len(selected) < max_edges:
        lcr = largest_component_ratio_from_pairs(selected, ctx.concept_labels)
        if lcr >= target_lcr:
            break
        comp_idx, comp_map = _component_index(selected, ctx.concept_labels)
        largest_id = -1
        largest_size = -1
        for cid, comp in comp_map.items():
            if len(comp) > largest_size:
                largest_size = len(comp)
                largest_id = cid
        best = None
        best_u = -10.0
        for item in pool:
            edge = item["edge"]
            key = edge_key(edge)
            if key in selected_keys:
                continue
            parent = edge["hypernym"]
            child = edge["hyponym"]
            score = float(edge.get("score", 0.0) or 0.0)
            if score < bridge_floor:
                continue
            if is_low_quality_label(parent) or is_low_quality_label(child):
                continue
            if parent_validity_score(parent, ctx.concept_doc_freq) < 0.38:
                continue
            pi = comp_idx.get(parent, -1)
            ci = comp_idx.get(child, -1)
            if pi == ci:
                continue
            touches_largest = int(pi == largest_id or ci == largest_id)
            if not touches_largest:
                continue
            if out_degree[parent] >= (parent_cap + 2):
                continue
            if _would_create_cycle(adjacency, parent, child):
                continue
            utility = score + (1.25 * float(ctx.settings.selector_connectivity_bonus))
            utility += method_adjust.get(item["method"], 0.0)
            if utility > best_u:
                best = edge
                best_u = utility
        if best is None:
            break
        add_edge(best)

    selected = dedupe_pairs(selected)
    selected = remove_cycles(selected)
    protected_raw = connectivity_critical_edge_keys(selected, ctx.concept_labels, ctx.concept_doc_freq)
    protected = cap_protected_edge_keys_by_parent(
        selected,
        protected_raw,
        ctx.concept_doc_freq,
        max_per_parent=max(1, ctx.settings.hubness_protected_max_per_parent),
    )
    selected = limit_parent_hubness(
        selected,
        ctx.concept_doc_freq,
        max_children_per_parent=max(parent_cap, ctx.settings.max_children_per_parent),
        protected_edge_keys=protected,
    )
    selected = collapse_bidirectional_pairs(selected, ctx.concept_doc_freq)

    stats = {
        "pool_size": len(pool),
        "selected": len(selected),
        "max_edges": max_edges,
        "score_floor": round(score_floor, 4),
        "bridge_floor": round(bridge_floor, 4),
        "target_lcr": round(target_lcr, 4),
        "final_lcr": round(largest_component_ratio_from_pairs(selected, ctx.concept_labels), 4),
        "method_mix": dict(Counter(edge_method(e) for e in selected)),
    }
    return selected, stats


def _selector_logs(
    ctx: BuildContext,
    pool: list[dict],
    selected_keys: set[tuple[str, str]],
    score_floor: float,
) -> list[dict]:
    logs: list[dict] = []
    for item in pool:
        edge = item["edge"]
        key = edge_key(edge)
        parent = edge["hypernym"]
        child = edge["hyponym"]
        parent_obj = ctx.concept_map.get(parent)
        child_obj = ctx.concept_map.get(child)
        score = float(edge.get("score", 0.0) or 0.0)
        decision = "accepted" if key in selected_keys else "rejected"
        rejection = None
        if decision == "rejected":
            rejection = "selector_score_below_floor" if score < score_floor else "selector_not_chosen"
        uncertainty = 1.0 - abs((2.0 * score) - 1.0)
        logs.append(
            {
                "taxonomy_version_id": ctx.taxonomy_version_id,
                "collection_id": ctx.collection_id,
                "parent_concept_id": str(parent_obj.id) if parent_obj else None,
                "child_concept_id": str(child_obj.id) if child_obj else None,
                "parent_label": parent,
                "child_label": child,
                "lang": _infer_lang(ctx, parent, child),
                "method": item.get("method", "unknown"),
                "stage": "selector_final",
                "base_score": score,
                "ranker_score": None,
                "evidence_score": None,
                "final_score": score,
                "decision": decision,
                "risk_score": max(0.0, min(1.0, uncertainty + (0.10 if rejection else 0.0))),
                "rejection_reason": rejection,
                "feature_vector": dict(item.get("feature_vector") or {}),
                "evidence": edge.get("evidence", {}),
                "min_score": score_floor,
            }
        )
    return logs


def apply_global_edge_selector(ctx: BuildContext, state: BuildState) -> dict:
    pool = _collect_candidate_pool(ctx, state)
    if not pool:
        state.selector_stats = {"enabled": True, "pool_size": 0, "selected": len(state.unique_pairs)}
        return state.selector_stats

    selected, stats = _select_edges(ctx, pool)
    if not selected:
        state.selector_stats = {
            "enabled": True,
            "pool_size": len(pool),
            "selected": len(state.unique_pairs),
            "fallback": True,
        }
        return state.selector_stats

    selected_keys = {edge_key(e) for e in selected}
    selector_logs = _selector_logs(
        ctx,
        pool,
        selected_keys=selected_keys,
        score_floor=float(ctx.settings.selector_score_floor),
    )
    state.candidate_logs.extend(selector_logs)
    state.unique_pairs = selected
    state.selector_stats = {
        "enabled": True,
        "fallback": False,
        **stats,
    }
    return state.selector_stats
