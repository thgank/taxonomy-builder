from __future__ import annotations

from collections import Counter

from app.config import config
from app.job_helper import add_job_event
from app.pipeline.taxonomy_build.build_types import BuildContext, BuildState
from app.pipeline.taxonomy_build.connectivity import anchor_connect_components
from app.pipeline.taxonomy_build.edge_filters import (
    edge_rejection_reason,
    parent_validity_score,
)
from app.pipeline.taxonomy_build.edge_scoring import (
    adaptive_bridge_budget,
    blend_scores,
    edge_min_score,
    threshold_from_profile,
)
from app.pipeline.taxonomy_build.build_generation import (
    build_candidate_log,
    extract_edge_features,
    predict_ranker_score,
)
from app.pipeline.taxonomy_build.graph_metrics import edge_key
from app.pipeline.taxonomy_build.pair_ops import compute_pair_cooccurrence
from app.pipeline.taxonomy_linking import bridge_components, safe_link_orphans
from app.pipeline.taxonomy_quality import compute_graph_quality


def _accept_new_edges(
    ctx: BuildContext,
    state: BuildState,
    current_pairs: list[dict],
    new_pairs: list[dict],
    stage: str,
    recovery_mode: bool = False,
) -> list[dict]:
    accepted: list[dict] = []
    existing_keys = {edge_key(e) for e in current_pairs}
    parent_degree: dict[str, int] = Counter(e["hypernym"] for e in current_pairs)
    cooc_support = compute_pair_cooccurrence(ctx.chunks, ctx.concept_labels)
    for e in new_pairs:
        key = edge_key(e)
        if key in existing_keys:
            continue
        features = extract_edge_features(ctx, e, cooc_support, parent_degree)
        min_score = edge_min_score(e, state.min_edge_accept_score, state.method_thresholds)
        if ctx.settings.adaptive_thresholds_enabled:
            min_score = threshold_from_profile(
                ctx.threshold_profile,
                method=str(features.get("method", "unknown")),
                lang=str(features.get("lang", "")),
                fallback=min_score,
            )

        evidence_score = (
            (0.65 * float(features.get("semantic_similarity", 0.0)))
            + (0.25 * float(features.get("lexical_similarity", 0.0)))
            + (0.10 * float(features.get("cooccurrence_support", 0.0)))
        )
        ranker_score = predict_ranker_score(ctx, features)
        if ranker_score is not None and ranker_score < ctx.settings.edge_ranker_min_confidence:
            ranker_score = None
        base_score = float(e.get("score", 0.0))
        e["score"] = round(
            blend_scores(
                base_score=base_score,
                ranker_score=ranker_score,
                evidence_score=evidence_score if ctx.settings.evidence_linking_enabled else None,
                ranker_alpha=ctx.settings.edge_ranker_blend_alpha,
                evidence_alpha=0.12,
            ),
            4,
        )
        ev = e.get("evidence", {})
        if isinstance(ev, dict):
            ev["semantic_similarity"] = round(float(features.get("semantic_similarity", 0.0) or 0.0), 4)
            ev["lexical_similarity"] = round(float(features.get("lexical_similarity", 0.0) or 0.0), 4)
            ev["cooccurrence_support"] = round(float(features.get("cooccurrence_support", 0.0) or 0.0), 4)
            ev["parent_validity"] = round(float(features.get("parent_validity", 0.0) or 0.0), 4)
            e["evidence"] = ev
        reason = edge_rejection_reason(e, ctx.concept_doc_freq, min_score, recovery_mode=recovery_mode)
        if reason:
            state.candidate_logs.append(
                build_candidate_log(
                    ctx,
                    e,
                    features,
                    decision="rejected",
                    rejection_reason=reason,
                    min_score=min_score,
                    ranker_score=ranker_score,
                    evidence_score=evidence_score if ctx.settings.evidence_linking_enabled else None,
                    stage=stage,
                )
            )
            continue
        accepted.append(e)
        state.candidate_logs.append(
            build_candidate_log(
                ctx,
                e,
                features,
                decision="accepted",
                rejection_reason=None,
                min_score=min_score,
                ranker_score=ranker_score,
                evidence_score=evidence_score if ctx.settings.evidence_linking_enabled else None,
                stage=stage,
            )
        )
        existing_keys.add(key)
        parent_degree[e["hypernym"]] = parent_degree.get(e["hypernym"], 0) + 1
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
            evidence_index=ctx.evidence_index if ctx.settings.evidence_linking_enabled else None,
            evidence_top_k=ctx.settings.evidence_top_k,
        )
        accepted_orphans = _accept_new_edges(
            ctx,
            state,
            state.unique_pairs,
            orphan_links,
            stage="orphan_linking",
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
                evidence_index=ctx.evidence_index if ctx.settings.evidence_linking_enabled else None,
                evidence_top_k=ctx.settings.evidence_top_k,
            )
            accepted_second = _accept_new_edges(
                ctx,
                state,
                state.unique_pairs,
                second_links,
                stage="orphan_linking_second_pass",
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
            max_new_children_per_parent=max(1, ctx.settings.bridge_max_new_children_per_parent),
            parent_load_penalty_alpha=max(0.0, ctx.settings.bridge_parent_load_penalty_alpha),
            evidence_index=ctx.evidence_index if ctx.settings.evidence_linking_enabled else None,
            evidence_top_k=ctx.settings.evidence_top_k,
        )
        accepted_bridges = _accept_new_edges(
            ctx,
            state,
            state.unique_pairs,
            bridges,
            stage=f"component_bridging_pass_{pass_idx}",
            recovery_mode=recovery_mode,
        )

        if accepted_bridges:
            state.connectivity_candidate_pool.extend(bridges)
            state.unique_pairs.extend(accepted_bridges)
            add_job_event(
                ctx.session,
                ctx.job_id,
                "INFO",
                f"Component bridging pass {pass_idx} added {len(accepted_bridges)}/{len(bridges)} edges "
                f"(threshold={effective_bridge_threshold:.2f}, budget={bridge_budget}, "
                f"recovery_mode={str(recovery_mode).lower()})",
            )
        else:
            add_job_event(
                ctx.session,
                ctx.job_id,
                "INFO",
                f"Component bridging pass {pass_idx} accepted 0/{len(bridges)} "
                f"(threshold={effective_bridge_threshold:.2f}, budget={bridge_budget}, "
                f"recovery_mode={str(recovery_mode).lower()})",
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
    dropped_parent_cap = 0
    current_parent_degree: dict[str, int] = Counter(e["hypernym"] for e in state.unique_pairs)
    local_parent_load: Counter[str] = Counter()
    parent_cap = max(1, ctx.settings.bridge_max_new_children_per_parent)
    parent_soft_cap = max(4, parent_cap + 2)
    adjusted_links: list[dict] = []
    for e in anchor_links:
        parent = e["hypernym"]
        if local_parent_load[parent] >= parent_cap:
            dropped_parent_cap += 1
            continue
        projected_parent_outdegree = current_parent_degree.get(parent, 0) + local_parent_load[parent]
        load_penalty = max(0.0, ctx.settings.bridge_parent_load_penalty_alpha) * max(
            0,
            projected_parent_outdegree - parent_soft_cap,
        )
        adjusted_edge = dict(e)
        adjusted_edge["score"] = round(max(0.0, float(e.get("score", 0.0)) - load_penalty), 4)
        evidence = adjusted_edge.get("evidence", {})
        if isinstance(evidence, dict):
            evidence["parent_load_penalty"] = round(load_penalty, 4)
            evidence["projected_parent_outdegree"] = projected_parent_outdegree
            adjusted_edge["evidence"] = evidence
        adjusted_links.append(adjusted_edge)
        local_parent_load[parent] += 1

    accepted_links = _accept_new_edges(
        ctx,
        state,
        state.unique_pairs,
        adjusted_links,
        stage="anchor_bridging",
        recovery_mode=recovery_mode,
    )

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
        + f"recovery_mode={str(recovery_mode).lower()}, parent_cap={dropped_parent_cap})",
    )
