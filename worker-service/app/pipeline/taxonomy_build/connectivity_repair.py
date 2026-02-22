from __future__ import annotations

import re
from collections import defaultdict

from app.pipeline.taxonomy_build.edge_filters import parent_validity_score
from app.pipeline.taxonomy_build.graph_metrics import (
    components_with_nodes,
    dedupe_pairs,
    edge_key,
    largest_component_ratio_from_pairs,
)
from app.pipeline.taxonomy_build.edge_scoring import edge_method
from app.pipeline.taxonomy_build.pair_ops import edge_rank_score
from app.pipeline.taxonomy_text import is_low_quality_label

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def trim_hub_edges(
    pairs: list[dict],
    concept_doc_freq: dict[str, int],
    max_outdegree: int,
    protected_edge_keys: set[tuple[str, str]] | None = None,
) -> tuple[list[dict], int, int]:
    if not pairs:
        return [], 0, 0
    if protected_edge_keys is None:
        protected_edge_keys = set()
    if max_outdegree <= 0:
        return pairs, 0, 0

    by_parent: dict[str, list[dict]] = defaultdict(list)
    degree: dict[str, int] = defaultdict(int)
    outdegree: dict[str, int] = defaultdict(int)
    node_set: set[str] = set()
    for e in pairs:
        by_parent[e["hypernym"]].append(e)
        degree[e["hypernym"]] += 1
        degree[e["hyponym"]] += 1
        outdegree[e["hypernym"]] += 1
        node_set.add(e["hypernym"])
        node_set.add(e["hyponym"])

    kept = list(pairs)
    removed = 0
    reattached = 0
    remove_keys: set[tuple[str, str]] = set()
    add_edges: list[dict] = []
    existing_keys = {edge_key(e) for e in pairs}

    def _lex(a: str, b: str) -> float:
        at = set(TOKEN_RE.findall(a.lower()))
        bt = set(TOKEN_RE.findall(b.lower()))
        if not at or not bt:
            return 0.0
        return len(at & bt) / max(1, len(at | bt))

    def _find_alternative_parent(child: str, old_parent: str) -> dict | None:
        candidates = sorted(
            (n for n in node_set if n not in {child, old_parent}),
            key=lambda n: (
                parent_validity_score(n, concept_doc_freq),
                -outdegree.get(n, 0),
                _lex(n, child),
                concept_doc_freq.get(n, 0),
            ),
            reverse=True,
        )
        for parent in candidates:
            if outdegree.get(parent, 0) >= max_outdegree:
                continue
            key = (parent, child)
            if key in existing_keys or key in remove_keys:
                continue
            if parent_validity_score(parent, concept_doc_freq) < 0.42:
                continue
            pt = TOKEN_RE.findall(parent.lower())
            ct = TOKEN_RE.findall(child.lower())
            if len(pt) == 1 and len(ct) == 1:
                continue
            score = max(0.62, min(0.84, 0.62 + (0.20 * _lex(parent, child))))
            return {
                "hypernym": parent,
                "hyponym": child,
                "score": round(score, 4),
                "evidence": {
                    "method": "hubness_rebalance_reattach",
                    "old_parent": old_parent,
                    "lexical_similarity": round(_lex(parent, child), 4),
                },
            }
        return None

    for parent, edges in by_parent.items():
        if len(edges) <= max_outdegree:
            continue
        ranked_asc = sorted(edges, key=lambda e: edge_rank_score(e, concept_doc_freq))
        to_remove = len(edges) - max_outdegree
        for e in ranked_asc:
            if to_remove <= 0:
                break
            k = edge_key(e)
            if k in protected_edge_keys:
                continue
            child = e["hyponym"]
            if degree.get(child, 0) <= 1:
                alt = _find_alternative_parent(child, parent)
                if not alt:
                    continue
                add_edges.append(alt)
                alt_parent = alt["hypernym"]
                alt_key = edge_key(alt)
                existing_keys.add(alt_key)
                outdegree[alt_parent] += 1
                degree[alt_parent] += 1
                degree[child] += 1
                node_set.add(alt_parent)
                reattached += 1
            if degree.get(parent, 0) <= 1:
                continue
            if k in remove_keys:
                continue
            remove_keys.add(k)
            degree[parent] = max(0, degree[parent] - 1)
            degree[child] = max(0, degree[child] - 1)
            outdegree[parent] = max(0, outdegree[parent] - 1)
            removed += 1
            to_remove -= 1

    if not remove_keys:
        if add_edges:
            kept.extend(add_edges)
            kept = dedupe_pairs(kept)
        return kept, 0, reattached
    kept = [e for e in kept if edge_key(e) not in remove_keys]
    if add_edges:
        kept.extend(add_edges)
        kept = dedupe_pairs(kept)
    return kept, removed, reattached


def repair_connectivity(
    current_pairs: list[dict],
    candidate_pairs: list[dict],
    concept_labels: list[str],
    concept_doc_freq: dict[str, int],
    target_lcr: float,
    max_additional_edges: int,
    target_component_count: int | None = None,
    recovery_mode: bool = False,
) -> tuple[list[dict], dict[str, int]]:
    stats: dict[str, int] = {
        "candidate_pairs_total": 0,
        "candidate_pairs_unique": 0,
        "iterations": 0,
        "considered": 0,
        "skipped_existing": 0,
        "skipped_low_score": 0,
        "skipped_low_quality_label": 0,
        "skipped_low_parent_validity": 0,
        "skipped_missing_component": 0,
        "skipped_same_component": 0,
        "selected": 0,
        "initial_component_count": 0,
        "final_component_count": 0,
    }
    if target_component_count is not None:
        stats["target_component_count"] = int(max(1, target_component_count))
    if max_additional_edges <= 0:
        return [], stats
    lcr = largest_component_ratio_from_pairs(current_pairs, concept_labels)
    initial_components = len(components_with_nodes(current_pairs, concept_labels))
    stats["initial_component_count"] = initial_components
    component_goal_met = (
        target_component_count is None or initial_components <= int(max(1, target_component_count))
    )
    if lcr >= target_lcr and component_goal_met:
        stats["final_component_count"] = initial_components
        return [], stats

    current_keys = {edge_key(e) for e in current_pairs}
    candidates = [e for e in candidate_pairs if edge_key(e) not in current_keys]
    stats["candidate_pairs_total"] = len(candidate_pairs)
    stats["candidate_pairs_unique"] = len(candidates)
    candidates.sort(key=lambda e: edge_rank_score(e, concept_doc_freq), reverse=True)
    repaired: list[dict] = []
    working = list(current_pairs)
    used_candidate_keys: set[tuple[str, str]] = set()

    while len(repaired) < max_additional_edges:
        stats["iterations"] += 1
        comps = components_with_nodes(working, concept_labels)
        if not comps:
            break
        comp_idx: dict[str, int] = {}
        comp_sizes: dict[int, int] = {}
        component_count = len(comps)
        need_component_reduction = (
            target_component_count is not None
            and component_count > int(max(1, target_component_count))
        )
        largest_comp_id = 0
        largest_comp_size = 0
        for i, comp in enumerate(comps):
            sz = len(comp)
            comp_sizes[i] = sz
            if sz > largest_comp_size:
                largest_comp_size = sz
                largest_comp_id = i
            for n in comp:
                comp_idx[n] = i

        best_edge = None
        best_priority = None
        for e in candidates:
            key = edge_key(e)
            if key in current_keys or key in used_candidate_keys:
                stats["skipped_existing"] += 1
                continue
            stats["considered"] += 1
            p = e["hypernym"]
            c = e["hyponym"]
            score = float(e.get("score", 0.0))
            post_lcr_phase = lcr >= target_lcr
            score_floor = 0.46 if recovery_mode else 0.50
            if post_lcr_phase:
                score_floor = 0.52 if recovery_mode else 0.56
            if score < score_floor:
                stats["skipped_low_score"] += 1
                continue
            if is_low_quality_label(p) or is_low_quality_label(c):
                stats["skipped_low_quality_label"] += 1
                continue
            method = edge_method(e)
            if post_lcr_phase and method == "connectivity_repair_fallback" and score < 0.60:
                stats["skipped_low_score"] += 1
                continue
            if post_lcr_phase and need_component_reduction and method == "connectivity_repair_fallback":
                stats["skipped_low_score"] += 1
                continue
            parent_floor = 0.34 if recovery_mode else 0.38
            if post_lcr_phase:
                parent_floor = max(parent_floor, 0.42)
            if parent_validity_score(p, concept_doc_freq) < parent_floor:
                stats["skipped_low_parent_validity"] += 1
                continue
            pi = comp_idx.get(p)
            ci = comp_idx.get(c)
            if pi is None or ci is None:
                stats["skipped_missing_component"] += 1
                continue
            if pi == ci:
                stats["skipped_same_component"] += 1
                continue
            merged_size = comp_sizes.get(pi, 0) + comp_sizes.get(ci, 0)
            touches_largest = int(pi == largest_comp_id or ci == largest_comp_id)
            bridges_small = int(comp_sizes.get(pi, 0) <= 3 or comp_sizes.get(ci, 0) <= 3)
            rank_score = edge_rank_score(e, concept_doc_freq)
            if lcr < target_lcr:
                priority = (touches_largest, merged_size, bridges_small, rank_score)
            elif need_component_reduction:
                priority = (bridges_small, merged_size, touches_largest, rank_score)
            else:
                priority = (touches_largest, merged_size, rank_score)
            if best_priority is None or priority > best_priority:
                best_priority = priority
                best_edge = e

        if not best_edge:
            stats["final_component_count"] = component_count
            break
        repaired.append(best_edge)
        working.append(best_edge)
        k = edge_key(best_edge)
        current_keys.add(k)
        used_candidate_keys.add(k)
        stats["selected"] += 1
        lcr = largest_component_ratio_from_pairs(working, concept_labels)
        new_component_count = len(components_with_nodes(working, concept_labels))
        stats["final_component_count"] = new_component_count
        component_goal_met = (
            target_component_count is None or new_component_count <= int(max(1, target_component_count))
        )
        if lcr >= target_lcr and component_goal_met:
            break
    if stats["final_component_count"] == 0:
        stats["final_component_count"] = len(components_with_nodes(working, concept_labels))
    return repaired, stats
