from __future__ import annotations

import re
from collections import Counter

from app.job_helper import add_job_event
from app.pipeline.taxonomy_build.build_types import BuildContext, BuildState
from app.pipeline.taxonomy_build.connectivity import (
    fallback_connectivity_candidates,
    fallback_semantic_connectivity_candidates,
    repair_connectivity,
    trim_hub_edges,
)
from app.pipeline.taxonomy_build.edge_filters import (
    connectivity_min_score,
    edge_rejection_reason,
    format_reason_counts,
    parent_validity_score,
)
from app.pipeline.taxonomy_build.edge_scoring import edge_method, edge_min_score
from app.pipeline.taxonomy_build.graph_metrics import (
    components_with_nodes,
    coverage_from_pairs,
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
from app.pipeline.taxonomy_linking import safe_link_orphans
from app.pipeline.taxonomy_quality import (
    compute_graph_quality,
    evaluate_quality_gate,
    remove_cycles,
)
from app.pipeline.taxonomy_text import is_low_quality_label, tokenize

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _max_parent_outdegree(pairs: list[dict]) -> int:
    if not pairs:
        return 0
    counts: Counter[str] = Counter()
    for edge in pairs:
        counts[edge["hypernym"]] += 1
    return max(counts.values(), default=0)


def _effective_target_lcr(
    ctx: BuildContext,
    state: BuildState,
    post_hub_lcr: float,
) -> tuple[float, dict[str, float | int | bool]]:
    base_target = float(ctx.settings.target_largest_component_ratio)
    if not ctx.settings.adaptive_target_lcr_enabled:
        return base_target, {
            "adaptive_enabled": False,
            "coverage": round(coverage_from_pairs(state.unique_pairs, ctx.concept_labels), 4),
            "component_count": len(components_with_nodes(state.unique_pairs, ctx.concept_labels)),
            "base_target": round(base_target, 4),
            "effective_target": round(base_target, 4),
        }

    coverage_now = coverage_from_pairs(state.unique_pairs, ctx.concept_labels)
    component_count = len(components_with_nodes(state.unique_pairs, ctx.concept_labels))
    severe_fragmentation = (
        component_count >= max(2, ctx.settings.adaptive_target_lcr_min_components)
        and post_hub_lcr < (base_target + ctx.settings.adaptive_target_lcr_gap_trigger)
    )
    if coverage_now >= ctx.settings.adaptive_target_lcr_min_coverage and severe_fragmentation:
        effective = max(base_target, float(ctx.settings.adaptive_target_lcr_value))
    else:
        effective = base_target
    return effective, {
        "adaptive_enabled": True,
        "coverage": round(coverage_now, 4),
        "component_count": component_count,
        "base_target": round(base_target, 4),
        "effective_target": round(effective, 4),
        "severe_fragmentation": severe_fragmentation,
    }


def _target_component_count(ctx: BuildContext, component_count: int) -> int | None:
    if not ctx.settings.adaptive_target_lcr_enabled:
        return None
    ratio = max(0.05, min(1.0, float(ctx.settings.adaptive_target_component_ratio)))
    dynamic_target = int(round(len(ctx.concept_labels) * ratio))
    target = max(int(ctx.settings.adaptive_target_component_min_count), dynamic_target)
    target = min(max(1, component_count), target)
    return target


def _lexical_similarity(a: str, b: str) -> float:
    at = set(TOKEN_RE.findall(a.lower()))
    bt = set(TOKEN_RE.findall(b.lower()))
    if not at or not bt:
        return 0.0
    return len(at & bt) / max(1, len(at | bt))


def _run_root_consolidation(ctx: BuildContext, state: BuildState) -> None:
    if not ctx.settings.root_consolidation_enabled:
        return

    parent_to_children: dict[str, set[str]] = {}
    parents: Counter[str] = Counter()
    children: Counter[str] = Counter()
    nodes: set[str] = set(ctx.concept_labels)
    for edge in state.unique_pairs:
        parent = edge["hypernym"]
        child = edge["hyponym"]
        parent_to_children.setdefault(parent, set()).add(child)
        parents[parent] += 1
        children[child] += 1
        nodes.add(parent)
        nodes.add(child)

    roots = [n for n in nodes if parents.get(n, 0) > 0 and children.get(n, 0) == 0]
    if not roots:
        return

    max_links = max(1, int(ctx.settings.root_consolidation_max_links))
    root_out_cap = max(1, int(ctx.settings.root_consolidation_max_root_outdegree))
    min_similarity = max(0.0, float(ctx.settings.root_consolidation_min_similarity))

    existing_keys = {edge_key(e) for e in state.unique_pairs}
    added: list[dict] = []
    rejected: Counter[str] = Counter()

    def _descendants(start: str) -> set[str]:
        seen: set[str] = set()
        stack = list(parent_to_children.get(start, set()))
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(parent_to_children.get(node, set()) - seen)
        return seen

    root_candidates = sorted(
        roots,
        key=lambda n: (parents.get(n, 0), -parent_validity_score(n, ctx.concept_doc_freq)),
    )
    for root in root_candidates:
        if len(added) >= max_links:
            break
        if parents.get(root, 0) > root_out_cap:
            continue
        blocked = _descendants(root) | {root}
        best_parent = None
        best_rank = -1.0
        root_tokens = tokenize(root)
        for candidate in nodes:
            if candidate in blocked:
                continue
            if parent_validity_score(candidate, ctx.concept_doc_freq) < 0.42:
                continue
            cand_tokens = tokenize(candidate)
            if not cand_tokens:
                continue
            lex = _lexical_similarity(candidate, root)
            contain = 1.0 if (candidate.lower() in root.lower() or root.lower() in candidate.lower()) else 0.0
            sim = (0.7 * lex) + (0.3 * contain)
            if sim < min_similarity and not (lex >= 0.10 and parent_validity_score(candidate, ctx.concept_doc_freq) >= 0.62):
                continue
            generality = 0.06 if len(cand_tokens) <= len(root_tokens) else -0.02
            hub_penalty = 0.02 * max(0, parents.get(candidate, 0) - 6)
            rank = sim + (0.20 * parent_validity_score(candidate, ctx.concept_doc_freq)) + generality - hub_penalty
            if rank > best_rank:
                best_rank = rank
                best_parent = candidate
        if not best_parent:
            continue
        candidate_edge = {
            "hypernym": best_parent,
            "hyponym": root,
            "score": round(max(0.52, min(0.84, 0.54 + (0.18 * best_rank))), 4),
            "evidence": {
                "method": "root_consolidation",
                "similarity": round(max(0.0, best_rank), 4),
            },
        }
        key = edge_key(candidate_edge)
        if key in existing_keys:
            continue
        min_score = connectivity_min_score(
            candidate_edge,
            edge_min_score(candidate_edge, state.min_edge_accept_score, state.method_thresholds),
            recovery_mode=True,
        )
        reason = edge_rejection_reason(
            candidate_edge,
            ctx.concept_doc_freq,
            min_score,
            recovery_mode=True,
        )
        if reason:
            rejected[reason] += 1
            continue
        existing_keys.add(key)
        parent_to_children.setdefault(best_parent, set()).add(root)
        parents[best_parent] += 1
        children[root] += 1
        added.append(candidate_edge)

    if added:
        state.unique_pairs.extend(added)
        state.unique_pairs = dedupe_pairs(state.unique_pairs)
        state.unique_pairs = collapse_bidirectional_pairs(state.unique_pairs, ctx.concept_doc_freq)
        state.unique_pairs = remove_cycles(state.unique_pairs)
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        f"Root consolidation added {len(added)}/{len(roots)} edges "
        f"(max_links={max_links}, rejected={format_reason_counts(rejected)})",
    )


def _run_orientation_sanity(ctx: BuildContext, state: BuildState) -> None:
    if not ctx.settings.orientation_sanity_enabled:
        return

    threshold = float(ctx.settings.orientation_sanity_low_score_threshold)
    max_rewrites = max(0, int(ctx.settings.orientation_sanity_max_rewrites))
    if max_rewrites == 0:
        return

    existing_keys = {edge_key(e) for e in state.unique_pairs}
    rewritten: list[dict] = []
    remove_keys: set[tuple[str, str]] = set()
    skipped_reasons: Counter[str] = Counter()
    candidate_methods = {
        "component_bridge",
        "component_anchor_bridge",
        "connectivity_repair_fallback",
        "embedding_clustering_relaxed",
        "hearst_trigger_fallback",
    }

    ranked_edges = sorted(state.unique_pairs, key=lambda e: float(e.get("score", 0.0)))
    for edge in ranked_edges:
        if len(rewritten) >= max_rewrites:
            break
        if float(edge.get("score", 0.0)) > threshold:
            break
        method = edge_method(edge)
        if method not in candidate_methods:
            continue
        parent = edge["hypernym"]
        child = edge["hyponym"]
        parent_tokens = tokenize(parent)
        child_tokens = tokenize(child)
        parent_valid = parent_validity_score(parent, ctx.concept_doc_freq)
        child_valid = parent_validity_score(child, ctx.concept_doc_freq)
        child_better_parent = child_valid >= (parent_valid + 0.10)
        lexical_subset = (
            len(parent_tokens) > len(child_tokens)
            and set(child_tokens).issubset(set(parent_tokens))
            and len(child_tokens) > 0
        )
        if not (child_better_parent or lexical_subset):
            skipped_reasons["not_suspicious"] += 1
            continue

        reversed_edge = dict(edge)
        reversed_edge["hypernym"] = child
        reversed_edge["hyponym"] = parent
        reversed_edge["score"] = round(min(0.88, max(float(edge.get("score", 0.0)) + 0.04, 0.56)), 4)
        evidence = reversed_edge.get("evidence", {})
        if isinstance(evidence, dict):
            evidence["method"] = "orientation_sanity_rewrite"
            evidence["original_method"] = method
            evidence["reason"] = "child_better_parent" if child_better_parent else "lexical_subset"
            reversed_edge["evidence"] = evidence
        rev_key = edge_key(reversed_edge)
        if rev_key in existing_keys:
            skipped_reasons["duplicate_reverse"] += 1
            continue
        min_score = edge_min_score(reversed_edge, state.min_edge_accept_score, state.method_thresholds)
        reason = edge_rejection_reason(reversed_edge, ctx.concept_doc_freq, min_score, recovery_mode=True)
        if reason:
            skipped_reasons[reason] += 1
            continue
        remove_keys.add(edge_key(edge))
        existing_keys.discard(edge_key(edge))
        existing_keys.add(rev_key)
        rewritten.append(reversed_edge)

    if rewritten:
        kept = [edge for edge in state.unique_pairs if edge_key(edge) not in remove_keys]
        kept.extend(rewritten)
        state.unique_pairs = dedupe_pairs(kept)
        state.unique_pairs = collapse_bidirectional_pairs(state.unique_pairs, ctx.concept_doc_freq)
        state.unique_pairs = remove_cycles(state.unique_pairs)
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        f"Orientation sanity rewrote {len(rewritten)} edges "
        f"(threshold={threshold:.2f}, max={max_rewrites}, skipped={format_reason_counts(skipped_reasons)})",
    )


def run_postprocess_and_recovery(ctx: BuildContext, state: BuildState) -> None:
    state.unique_pairs = dedupe_pairs(state.unique_pairs)
    state.unique_pairs = collapse_bidirectional_pairs(state.unique_pairs, ctx.concept_doc_freq)

    pre_prune_pairs = list(state.unique_pairs)
    pre_prune_lcr = largest_component_ratio_from_pairs(pre_prune_pairs, ctx.concept_labels)
    protected_keys = connectivity_critical_edge_keys(pre_prune_pairs, ctx.concept_labels, ctx.concept_doc_freq)
    state.unique_pairs = limit_parent_hubness(
        state.unique_pairs,
        ctx.concept_doc_freq,
        max_children_per_parent=ctx.settings.max_children_per_parent,
        protected_edge_keys=protected_keys,
    )
    post_hub_lcr = largest_component_ratio_from_pairs(state.unique_pairs, ctx.concept_labels)
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        f"Post-processing LCR: pre_prune={pre_prune_lcr:.3f}, post_hub={post_hub_lcr:.3f}, "
        f"protected_edges={len(protected_keys)}",
    )

    _run_connectivity_repair(ctx, state, pre_prune_pairs, post_hub_lcr)
    _run_root_consolidation(ctx, state)
    _run_orientation_sanity(ctx, state)
    _run_coverage_recovery(ctx, state)


def _run_connectivity_repair(
    ctx: BuildContext,
    state: BuildState,
    pre_prune_pairs: list[dict],
    post_hub_lcr: float,
) -> None:
    if not ctx.settings.connectivity_repair_enabled:
        return

    effective_target_lcr, target_info = _effective_target_lcr(ctx, state, post_hub_lcr)
    target_component_count = _target_component_count(ctx, int(target_info["component_count"]))
    component_goal_met = (
        target_component_count is None or int(target_info["component_count"]) <= target_component_count
    )
    if post_hub_lcr >= effective_target_lcr and component_goal_met:
        return

    recovery_mode = (
        ctx.settings.lcr_recovery_mode_enabled
        and post_hub_lcr < (effective_target_lcr - ctx.settings.lcr_recovery_margin)
    )
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        "Connectivity repair target: "
        f"base={target_info['base_target']:.3f}, "
        f"effective={target_info['effective_target']:.3f}, "
        f"coverage={target_info['coverage']:.3f}, "
        f"components={target_info['component_count']}, "
        f"component_target={target_component_count if target_component_count is not None else 'none'}, "
        f"adaptive={str(target_info['adaptive_enabled']).lower()}",
    )
    fallback_repair_candidates = fallback_connectivity_candidates(
        state.unique_pairs,
        concept_labels=ctx.concept_labels,
        concept_doc_freq=ctx.concept_doc_freq,
        max_links=max(10, len(ctx.concepts) // 2),
    )
    fallback_semantic_candidates = fallback_semantic_connectivity_candidates(
        state.unique_pairs,
        concept_labels=ctx.concept_labels,
        concept_doc_freq=ctx.concept_doc_freq,
        max_links=max(10, len(ctx.concepts) // 2),
    )
    if fallback_repair_candidates:
        state.connectivity_candidate_pool.extend(fallback_repair_candidates)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Connectivity repair fallback generated {len(fallback_repair_candidates)} "
            "largest-component candidates",
        )
    if fallback_semantic_candidates:
        state.connectivity_candidate_pool.extend(fallback_semantic_candidates)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Connectivity repair semantic fallback generated {len(fallback_semantic_candidates)} "
            "largest-component candidates",
        )

    repaired, repair_stats = repair_connectivity(
        current_pairs=state.unique_pairs,
        candidate_pairs=state.connectivity_candidate_pool + pre_prune_pairs,
        concept_labels=ctx.concept_labels,
        concept_doc_freq=ctx.concept_doc_freq,
        target_lcr=effective_target_lcr,
        max_additional_edges=ctx.settings.connectivity_repair_max_links,
        target_component_count=target_component_count,
        recovery_mode=recovery_mode,
    )
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        "Connectivity repair diagnostics: "
        f"recovery_mode={str(recovery_mode).lower()}, "
        f"selected={repair_stats.get('selected', 0)}, "
        f"unique_candidates={repair_stats.get('candidate_pairs_unique', 0)}, "
        f"considered={repair_stats.get('considered', 0)}, "
        f"skip_existing={repair_stats.get('skipped_existing', 0)}, "
        f"skip_same_component={repair_stats.get('skipped_same_component', 0)}, "
        f"skip_low_parent={repair_stats.get('skipped_low_parent_validity', 0)}, "
        f"skip_low_quality={repair_stats.get('skipped_low_quality_label', 0)}, "
        f"skip_low_score={repair_stats.get('skipped_low_score', 0)}, "
        f"components={repair_stats.get('initial_component_count', 0)}->"
        f"{repair_stats.get('final_component_count', 0)}"
        + (
            f"/{repair_stats.get('target_component_count', 0)}"
            if repair_stats.get("target_component_count", 0) > 0
            else ""
        ),
    )
    if repaired:
        state.unique_pairs.extend(repaired)
        state.unique_pairs = dedupe_pairs(state.unique_pairs)
        state.unique_pairs = collapse_bidirectional_pairs(state.unique_pairs, ctx.concept_doc_freq)
        post_repair_lcr = largest_component_ratio_from_pairs(state.unique_pairs, ctx.concept_labels)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Connectivity repair added {len(repaired)} edges; "
            f"post_repair_lcr={post_repair_lcr:.3f} (target={effective_target_lcr:.3f})",
        )


def _run_coverage_recovery(ctx: BuildContext, state: BuildState) -> None:
    if not ctx.settings.coverage_recovery_enabled:
        return

    coverage_now = coverage_from_pairs(state.unique_pairs, ctx.concept_labels)
    accepted_recovery_orphans: list[dict] = []
    rejected_reasons: Counter[str] = Counter()
    recovery_orphans_total = 0
    existing_keys = {edge_key(e) for e in state.unique_pairs}

    def _accept_recovery_links(candidates: list[dict]) -> list[dict]:
        accepted: list[dict] = []
        nonlocal recovery_orphans_total
        recovery_orphans_total += len(candidates)
        for e in candidates:
            if edge_key(e) in existing_keys:
                continue
            min_score = connectivity_min_score(
                e,
                edge_min_score(e, state.min_edge_accept_score, state.method_thresholds),
                recovery_mode=True,
            )
            reason = edge_rejection_reason(e, ctx.concept_doc_freq, min_score, recovery_mode=True)
            if reason:
                rejected_reasons[reason] += 1
                continue
            accepted.append(e)
            existing_keys.add(edge_key(e))
        return accepted

    if coverage_now < ctx.settings.coverage_recovery_target:
        recovery_orphans = safe_link_orphans(
            state.unique_pairs,
            ctx.concept_labels,
            threshold=max(0.44, ctx.settings.orphan_link_threshold - 0.10),
            max_links=ctx.settings.coverage_recovery_max_links,
            parent_validator=lambda lbl: parent_validity_score(lbl, ctx.concept_doc_freq),
            concept_doc_freq=ctx.concept_doc_freq,
            concept_scores=ctx.concept_scores,
            min_orphan_doc_freq=1,
            min_orphan_score=0.15,
        )
        accepted_recovery_orphans.extend(_accept_recovery_links(recovery_orphans))
        if accepted_recovery_orphans:
            state.unique_pairs.extend(accepted_recovery_orphans)
            state.unique_pairs = dedupe_pairs(state.unique_pairs)
            state.unique_pairs = collapse_bidirectional_pairs(state.unique_pairs, ctx.concept_doc_freq)

        coverage_after = coverage_from_pairs(state.unique_pairs, ctx.concept_labels)
        if coverage_after < ctx.settings.coverage_recovery_target:
            second_pass = safe_link_orphans(
                state.unique_pairs,
                ctx.concept_labels,
                threshold=max(0.38, ctx.settings.orphan_link_threshold - 0.16),
                max_links=max(4, ctx.settings.coverage_recovery_max_links // 2),
                parent_validator=lambda lbl: parent_validity_score(lbl, ctx.concept_doc_freq),
                concept_doc_freq=ctx.concept_doc_freq,
                concept_scores=ctx.concept_scores,
                min_orphan_doc_freq=1,
                min_orphan_score=0.0,
            )
            accepted_second = _accept_recovery_links(second_pass)
            if accepted_second:
                accepted_recovery_orphans.extend(accepted_second)
                state.unique_pairs.extend(accepted_second)
                state.unique_pairs = dedupe_pairs(state.unique_pairs)
                state.unique_pairs = collapse_bidirectional_pairs(state.unique_pairs, ctx.concept_doc_freq)
            coverage_after = coverage_from_pairs(state.unique_pairs, ctx.concept_labels)

        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Coverage recovery added {len(accepted_recovery_orphans)}/{recovery_orphans_total} edges "
            f"(target={ctx.settings.coverage_recovery_target:.3f}, before={coverage_now:.3f}, "
            f"after={coverage_after:.3f}, rejected={format_reason_counts(rejected_reasons)})",
        )


def evaluate_quality_gate_and_hubness(ctx: BuildContext, state: BuildState) -> tuple[dict, list[str]]:
    quality_candidate_count = sum(
        1
        for c in ctx.concepts
        if not is_low_quality_label(c.canonical) and ctx.concept_doc_freq.get(c.canonical, 0) >= 2
    )
    quality_total = max(1, quality_candidate_count)
    pre_hubness_quality = compute_graph_quality(state.unique_pairs, quality_total)

    if pre_hubness_quality["hubness"] > ctx.settings.quality_thresholds["max_hubness"]:
        hub_cap = int(max(2, round(ctx.settings.quality_thresholds["max_hubness"])))
        protected_for_hubness_raw = connectivity_critical_edge_keys(
            state.unique_pairs,
            ctx.concept_labels,
            ctx.concept_doc_freq,
        )
        protected_for_hubness = cap_protected_edge_keys_by_parent(
            state.unique_pairs,
            protected_for_hubness_raw,
            ctx.concept_doc_freq,
            max_per_parent=max(1, ctx.settings.hubness_protected_max_per_parent),
        )
        max_out_before = _max_parent_outdegree(state.unique_pairs)
        state.unique_pairs, removed_hub_edges, reattached_hub_edges = trim_hub_edges(
            state.unique_pairs,
            ctx.concept_doc_freq,
            max_outdegree=hub_cap,
            protected_edge_keys=protected_for_hubness,
        )
        state.unique_pairs = collapse_bidirectional_pairs(state.unique_pairs, ctx.concept_doc_freq)
        post_hubness_quality = compute_graph_quality(state.unique_pairs, quality_total)
        max_out_after = _max_parent_outdegree(state.unique_pairs)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Hubness rebalance removed {removed_hub_edges} edges, reattached {reattached_hub_edges} "
            f"(hubness {pre_hubness_quality['hubness']:.3f} -> {post_hubness_quality['hubness']:.3f}, "
            f"max_outdegree {max_out_before} -> {max_out_after}, "
            f"protected_edges {len(protected_for_hubness_raw)} -> {len(protected_for_hubness)})",
        )

    quality_report = compute_graph_quality(state.unique_pairs, quality_total)
    violations = evaluate_quality_gate(quality_report, ctx.settings.quality_thresholds)
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        "Quality gate metrics: "
        f"edge_density={quality_report['edge_density']:.3f}, "
        f"largest_component_ratio={quality_report['largest_component_ratio']:.3f}, "
        f"hubness={quality_report['hubness']:.3f}, "
        f"lexical_noise_rate={quality_report['lexical_noise_rate']:.3f}",
    )
    return quality_report, violations
