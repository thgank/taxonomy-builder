from __future__ import annotations

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
from app.pipeline.taxonomy_build.edge_scoring import edge_min_score
from app.pipeline.taxonomy_build.graph_metrics import (
    coverage_from_pairs,
    dedupe_pairs,
    edge_key,
    largest_component_ratio_from_pairs,
)
from app.pipeline.taxonomy_build.pair_ops import (
    collapse_bidirectional_pairs,
    connectivity_critical_edge_keys,
    limit_parent_hubness,
)
from app.pipeline.taxonomy_linking import safe_link_orphans
from app.pipeline.taxonomy_quality import (
    compute_graph_quality,
    evaluate_quality_gate,
)
from app.pipeline.taxonomy_text import is_low_quality_label


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
    _run_coverage_recovery(ctx, state)


def _run_connectivity_repair(
    ctx: BuildContext,
    state: BuildState,
    pre_prune_pairs: list[dict],
    post_hub_lcr: float,
) -> None:
    if not ctx.settings.connectivity_repair_enabled:
        return
    if post_hub_lcr >= ctx.settings.target_largest_component_ratio:
        return

    recovery_mode = (
        ctx.settings.lcr_recovery_mode_enabled
        and post_hub_lcr < (ctx.settings.target_largest_component_ratio - ctx.settings.lcr_recovery_margin)
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
        target_lcr=ctx.settings.target_largest_component_ratio,
        max_additional_edges=ctx.settings.connectivity_repair_max_links,
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
        f"skip_low_score={repair_stats.get('skipped_low_score', 0)}",
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
            f"post_repair_lcr={post_repair_lcr:.3f} (target={ctx.settings.target_largest_component_ratio:.3f})",
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
        protected_for_hubness = connectivity_critical_edge_keys(
            state.unique_pairs,
            ctx.concept_labels,
            ctx.concept_doc_freq,
        )
        state.unique_pairs, removed_hub_edges, reattached_hub_edges = trim_hub_edges(
            state.unique_pairs,
            ctx.concept_doc_freq,
            max_outdegree=hub_cap,
            protected_edge_keys=protected_for_hubness,
        )
        state.unique_pairs = collapse_bidirectional_pairs(state.unique_pairs, ctx.concept_doc_freq)
        post_hubness_quality = compute_graph_quality(state.unique_pairs, quality_total)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Hubness rebalance removed {removed_hub_edges} edges, reattached {reattached_hub_edges} "
            f"(hubness {pre_hubness_quality['hubness']:.3f} -> {post_hubness_quality['hubness']:.3f})",
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
