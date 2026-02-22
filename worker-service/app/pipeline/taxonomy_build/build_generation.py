from __future__ import annotations

from app.config import config
from app.job_helper import add_job_event, update_job_status
from app.pipeline.taxonomy_build.build_types import BuildContext, BuildState
from app.pipeline.taxonomy_build.edge_filters import is_edge_plausible, parent_validity_score
from app.pipeline.taxonomy_build.edge_scoring import (
    adaptive_method_thresholds,
    edge_method,
    edge_min_score,
)
from app.pipeline.taxonomy_build.pair_ops import (
    collapse_bidirectional_pairs,
    compute_pair_cooccurrence,
    method_weight,
)
from app.pipeline.taxonomy_embedding import build_embedding_hierarchy
from app.pipeline.taxonomy_quality import limit_depth, remove_cycles
from app.pipeline.taxonomy_text import extract_hearst_pairs


def _merge_duplicate_pairs(pairs: list[dict]) -> list[dict]:
    seen_pairs: set[tuple[str, str]] = set()
    unique_pairs: list[dict] = []
    for pair in pairs:
        key = (pair["hypernym"], pair["hyponym"])
        if key not in seen_pairs:
            seen_pairs.add(key)
            unique_pairs.append(pair)
            continue
        for up in unique_pairs:
            if (up["hypernym"], up["hyponym"]) != key:
                continue
            up["score"] = max(up["score"], pair["score"])
            up_evidence = up.get("evidence", [])
            pair_evidence = pair.get("evidence", [])
            if isinstance(up_evidence, dict):
                up_evidence = [up_evidence]
            if isinstance(pair_evidence, dict):
                pair_evidence = [pair_evidence]
            up["evidence"] = up_evidence + pair_evidence
            break
    return unique_pairs


def build_all_relation_candidates(ctx: BuildContext) -> list[dict]:
    all_pairs: list[dict] = []
    concept_set = set(ctx.concept_labels)
    if ctx.method in ("hearst", "hybrid"):
        hearst_pairs: list[dict] = []
        hearst_soft_pairs: list[dict] = []
        for lang, group_chunks in ctx.lang_groups.items():
            hearst_pairs.extend(extract_hearst_pairs(group_chunks, concept_set, lang, soft_mode=False))
            if ctx.settings.hearst_soft_mode:
                hearst_soft_pairs.extend(
                    extract_hearst_pairs(group_chunks, concept_set, lang, soft_mode=True)
                )
        if hearst_soft_pairs:
            hearst_pairs.extend(hearst_soft_pairs)
        all_pairs.extend(hearst_pairs)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Hearst patterns found {len(hearst_pairs)} relations across langs={ctx.lang_counts} "
            f"(soft_mode={ctx.settings.hearst_soft_mode})",
        )
        update_job_status(ctx.session, ctx.job_id, "RUNNING", progress=30)

    if ctx.method in ("embedding", "hybrid"):
        emb_pairs = build_embedding_hierarchy(
            ctx.concepts,
            ctx.settings.sim_threshold,
            parent_pool_size=ctx.settings.parent_pool_size,
            max_children_per_parent=ctx.settings.max_children_per_parent,
            adaptive_percentile=ctx.settings.adaptive_percentile,
            concept_doc_freq=ctx.concept_doc_freq,
            min_parent_doc_freq=ctx.settings.min_parent_doc_freq,
        )
        all_pairs.extend(emb_pairs)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Embedding clustering found {len(emb_pairs)} relations",
        )
        update_job_status(ctx.session, ctx.job_id, "RUNNING", progress=60)
    return all_pairs


def build_initial_state(ctx: BuildContext, all_pairs: list[dict]) -> BuildState:
    unique_pairs = _merge_duplicate_pairs(all_pairs)
    unique_pairs = collapse_bidirectional_pairs(unique_pairs, ctx.concept_doc_freq)
    unique_pairs = remove_cycles(unique_pairs)
    unique_pairs = limit_depth(unique_pairs, ctx.settings.max_depth)

    min_edge_accept_score = float(
        ctx.params.get("min_edge_accept_score", config.min_edge_accept_score)
    )
    method_thresholds = adaptive_method_thresholds(
        unique_pairs,
        min_edge_accept_score,
        ctx.settings.adaptive_edge_accept_percentile,
    )
    unique_pairs = [
        e
        for e in unique_pairs
        if is_edge_plausible(
            e,
            ctx.concept_doc_freq,
            edge_min_score(e, min_edge_accept_score, method_thresholds),
        )
    ]
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        f"Adaptive edge accept thresholds: default={min_edge_accept_score:.2f}, "
        f"per_method={method_thresholds}",
    )

    cooc_support = compute_pair_cooccurrence(ctx.chunks, ctx.concept_labels)
    for e in unique_pairs:
        base = float(e.get("score", 0.0))
        cooc = float(cooc_support.get((e["hypernym"], e["hyponym"]), 0.0))
        method_w = method_weight(edge_method(e))
        parent_validity = parent_validity_score(e["hypernym"], ctx.concept_doc_freq)
        composite = max(0.0, min(1.0, (method_w * base) + (0.20 * cooc) + (0.18 * parent_validity)))
        e["score"] = round(composite, 4)
        ev = e.get("evidence", {})
        if isinstance(ev, dict):
            ev["cooccurrence_support"] = round(cooc, 4)
            ev["parent_validity"] = round(parent_validity, 4)
            ev["composite_score"] = round(composite, 4)
            e["evidence"] = ev

    return BuildState(
        unique_pairs=unique_pairs,
        connectivity_candidate_pool=[],
        min_edge_accept_score=min_edge_accept_score,
        method_thresholds=method_thresholds,
    )
