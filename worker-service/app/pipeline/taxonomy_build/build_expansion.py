from __future__ import annotations

from collections import Counter

from app.config import config
from app.job_helper import add_job_event
from app.pipeline.taxonomy_build.build_types import BuildContext, BuildState
from app.pipeline.taxonomy_build.connectivity import anchor_connect_components
from app.pipeline.taxonomy_build.edge_filters import (
    connectivity_min_score,
    edge_rejection_reason,
    format_reason_counts,
    is_edge_plausible,
    parent_validity_score,
)
from app.pipeline.taxonomy_build.edge_scoring import adaptive_bridge_budget, edge_min_score
from app.pipeline.taxonomy_build.graph_metrics import edge_key
from app.pipeline.taxonomy_linking import bridge_components, safe_link_orphans
from app.pipeline.taxonomy_quality import compute_graph_quality


def _accept_new_edges(
    current_pairs: list[dict],
    new_pairs: list[dict],
    concept_doc_freq: dict[str, int],
    min_edge_accept_score: float,
    method_thresholds: dict[str, float],
) -> list[dict]:
    accepted: list[dict] = []
    existing_keys = {edge_key(e) for e in current_pairs}
    for e in new_pairs:
        key = edge_key(e)
        if key in existing_keys:
            continue
        if not is_edge_plausible(
            e,
            concept_doc_freq,
            edge_min_score(e, min_edge_accept_score, method_thresholds),
        ):
            continue
        accepted.append(e)
        existing_keys.add(key)
    return accepted


def apply_connectivity_expansion(ctx: BuildContext, state: BuildState) -> None:
    if ctx.settings.orphan_linking_enabled:
        orphan_links = safe_link_orphans(
            state.unique_pairs,
            ctx.concept_labels,
            threshold=ctx.settings.orphan_link_threshold,
            max_links=ctx.settings.orphan_link_max_links,
            parent_validator=lambda lbl: parent_validity_score(lbl, ctx.concept_doc_freq),
            concept_doc_freq=ctx.concept_doc_freq,
            concept_scores=ctx.concept_scores,
            min_orphan_doc_freq=2,
            min_orphan_score=0.25,
        )
        accepted_orphans = _accept_new_edges(
            state.unique_pairs,
            orphan_links,
            ctx.concept_doc_freq,
            state.min_edge_accept_score,
            state.method_thresholds,
        )
        if accepted_orphans:
            state.unique_pairs.extend(accepted_orphans)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Orphan safe-linking added {len(accepted_orphans)} edges "
            f"(threshold={ctx.settings.orphan_link_threshold:.2f})",
        )

        interim_quality = compute_graph_quality(state.unique_pairs, len(ctx.concepts))
        if interim_quality["largest_component_ratio"] < 0.20:
            second_threshold = max(0.50, ctx.settings.orphan_link_threshold - 0.06)
            second_links = safe_link_orphans(
                state.unique_pairs,
                ctx.concept_labels,
                threshold=second_threshold,
                max_links=max(5, ctx.settings.orphan_link_max_links // 2),
                parent_validator=lambda lbl: parent_validity_score(lbl, ctx.concept_doc_freq),
                concept_doc_freq=ctx.concept_doc_freq,
                concept_scores=ctx.concept_scores,
                min_orphan_doc_freq=2,
                min_orphan_score=0.25,
            )
            accepted_second = _accept_new_edges(
                state.unique_pairs,
                second_links,
                ctx.concept_doc_freq,
                state.min_edge_accept_score,
                state.method_thresholds,
            )
            if accepted_second:
                state.unique_pairs.extend(accepted_second)
            add_job_event(
                ctx.session,
                ctx.job_id,
                "INFO",
                f"Orphan safe-linking second pass added {len(accepted_second)} edges "
                f"(threshold={second_threshold:.2f})",
            )

    _run_component_bridging(ctx, state)
    _run_anchor_bridging(ctx, state)


def _run_component_bridging(ctx: BuildContext, state: BuildState) -> None:
    if not ctx.settings.component_bridging_enabled:
        return

    interim_quality = compute_graph_quality(state.unique_pairs, len(ctx.concepts))
    if interim_quality["largest_component_ratio"] >= max(0.55, ctx.settings.target_largest_component_ratio):
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            "Component bridging skipped (graph already sufficiently connected)",
        )
        return

    effective_bridge_threshold = ctx.settings.component_bridge_threshold
    for pass_idx in range(1, 4):
        interim_quality = compute_graph_quality(state.unique_pairs, len(ctx.concepts))
        if interim_quality["largest_component_ratio"] >= ctx.settings.target_largest_component_ratio:
            break
        recovery_mode = (
            ctx.settings.lcr_recovery_mode_enabled
            and interim_quality["largest_component_ratio"]
            < (ctx.settings.target_largest_component_ratio - ctx.settings.lcr_recovery_margin)
        )
        bridge_budget = adaptive_bridge_budget(
            base_budget=ctx.settings.component_bridge_max_links,
            concept_count=len(ctx.concepts),
            current_lcr=interim_quality["largest_component_ratio"],
            target_lcr=ctx.settings.target_largest_component_ratio,
        )
        bridges = bridge_components(
            state.unique_pairs,
            threshold=effective_bridge_threshold,
            max_links=bridge_budget,
            concept_labels=ctx.concept_labels,
            parent_validator=lambda lbl: parent_validity_score(lbl, ctx.concept_doc_freq),
            min_lexical_similarity=max(
                0.16,
                float(config.min_bridge_lexical_similarity) - (0.04 * (pass_idx - 1)),
            ),
            min_semantic_similarity=max(
                0.62,
                float(config.min_bridge_semantic_similarity) - (0.08 * (pass_idx - 1)),
            ),
        )
        rejected_reasons: Counter[str] = Counter()
        dropped_duplicate = 0
        existing_keys = {edge_key(e) for e in state.unique_pairs}
        accepted_bridges: list[dict] = []
        for e in bridges:
            min_score = connectivity_min_score(
                e,
                edge_min_score(e, state.min_edge_accept_score, state.method_thresholds),
                recovery_mode=recovery_mode,
            )
            reason = edge_rejection_reason(
                e,
                ctx.concept_doc_freq,
                min_score,
                recovery_mode=recovery_mode,
            )
            if reason:
                rejected_reasons[reason] += 1
                continue
            if edge_key(e) in existing_keys:
                dropped_duplicate += 1
                continue
            accepted_bridges.append(e)
            existing_keys.add(edge_key(e))

        if accepted_bridges:
            state.connectivity_candidate_pool.extend(bridges)
            state.unique_pairs.extend(accepted_bridges)
            add_job_event(
                ctx.session,
                ctx.job_id,
                "INFO",
                f"Component bridging pass {pass_idx} added {len(accepted_bridges)}/{len(bridges)} edges "
                f"(threshold={effective_bridge_threshold:.2f}, budget={bridge_budget}, "
                f"recovery_mode={str(recovery_mode).lower()}, "
                f"duplicates={dropped_duplicate}, rejected={format_reason_counts(rejected_reasons)})",
            )
        else:
            add_job_event(
                ctx.session,
                ctx.job_id,
                "INFO",
                f"Component bridging pass {pass_idx} accepted 0/{len(bridges)} "
                f"(threshold={effective_bridge_threshold:.2f}, budget={bridge_budget}, "
                f"recovery_mode={str(recovery_mode).lower()}, "
                f"duplicates={dropped_duplicate}, rejected={format_reason_counts(rejected_reasons)})",
            )
            effective_bridge_threshold = max(0.48, effective_bridge_threshold - 0.04)
            continue
        effective_bridge_threshold = max(0.48, effective_bridge_threshold - 0.03)


def _run_anchor_bridging(ctx: BuildContext, state: BuildState) -> None:
    if not ctx.settings.anchor_bridging_enabled:
        return
    interim_quality = compute_graph_quality(state.unique_pairs, len(ctx.concepts))
    if interim_quality["largest_component_ratio"] >= ctx.settings.target_largest_component_ratio:
        return

    recovery_mode = (
        ctx.settings.lcr_recovery_mode_enabled
        and interim_quality["largest_component_ratio"]
        < (ctx.settings.target_largest_component_ratio - ctx.settings.lcr_recovery_margin)
    )
    anchor_links = anchor_connect_components(
        state.unique_pairs,
        concept_labels=ctx.concept_labels,
        concept_doc_freq=ctx.concept_doc_freq,
        target_lcr=ctx.settings.target_largest_component_ratio,
        max_links=ctx.settings.anchor_bridge_max_links,
    )
    rejected_reasons: Counter[str] = Counter()
    dropped_duplicate = 0
    existing_keys = {edge_key(e) for e in state.unique_pairs}
    accepted_links: list[dict] = []
    for e in anchor_links:
        min_score = connectivity_min_score(
            e,
            edge_min_score(e, state.min_edge_accept_score, state.method_thresholds),
            recovery_mode=recovery_mode,
        )
        reason = edge_rejection_reason(e, ctx.concept_doc_freq, min_score, recovery_mode=recovery_mode)
        if reason:
            rejected_reasons[reason] += 1
            continue
        if edge_key(e) in existing_keys:
            dropped_duplicate += 1
            continue
        accepted_links.append(e)
        existing_keys.add(edge_key(e))

    if accepted_links:
        state.connectivity_candidate_pool.extend(anchor_links)
        state.unique_pairs.extend(accepted_links)
        msg = f"Anchor component bridging added {len(accepted_links)}/{len(anchor_links)} edges "
    else:
        msg = f"Anchor component bridging accepted 0/{len(anchor_links)} "
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        msg
        + f"(target_lcr={ctx.settings.target_largest_component_ratio:.2f}, budget={ctx.settings.anchor_bridge_max_links}, "
        + f"recovery_mode={str(recovery_mode).lower()}, duplicates={dropped_duplicate}, "
        + f"rejected={format_reason_counts(rejected_reasons)})",
    )
