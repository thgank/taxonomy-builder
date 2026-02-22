from __future__ import annotations

from app.config import config
from app.job_helper import add_job_event, update_job_status
from app.pipeline.taxonomy_build.build_types import BuildContext, BuildState
from app.pipeline.taxonomy_build.edge_filters import edge_rejection_reason, parent_validity_score
from app.pipeline.taxonomy_build.edge_scoring import (
    adaptive_method_thresholds,
    blend_scores,
    edge_method,
    edge_min_score,
    threshold_from_profile,
)
from app.pipeline.taxonomy_build.pair_ops import (
    collapse_bidirectional_pairs,
    compute_pair_cooccurrence,
    method_weight,
)
from app.pipeline.taxonomy_embedding import build_embedding_hierarchy
from app.pipeline.taxonomy_quality import limit_depth, remove_cycles
from app.pipeline.taxonomy_text import extract_hearst_pairs, extract_hearst_trigger_pairs, tokenize


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


def _token_jaccard(a: str, b: str) -> float:
    at = set(tokenize(a))
    bt = set(tokenize(b))
    if not at or not bt:
        return 0.0
    return len(at & bt) / max(1, len(at | bt))


def _evidence_value(edge: dict, key: str) -> float:
    ev = edge.get("evidence", [])
    if isinstance(ev, dict):
        ev = [ev]
    best = 0.0
    for item in ev:
        if not isinstance(item, dict):
            continue
        best = max(best, float(item.get(key, 0.0) or 0.0))
    return best


def _infer_edge_lang(ctx: BuildContext, parent_label: str, child_label: str) -> str:
    parent = ctx.concept_map.get(parent_label)
    child = ctx.concept_map.get(child_label)
    lang = (parent.lang if parent else None) or (child.lang if child else None) or ctx.dominant_lang or "en"
    return (lang or "en").lower()[:2]


def extract_edge_features(
    ctx: BuildContext,
    edge: dict,
    cooc_support: dict[tuple[str, str], float],
    parent_degree: dict[str, int],
) -> dict[str, float | str]:
    parent = edge["hypernym"]
    child = edge["hyponym"]
    method = edge_method(edge)
    parent_df = float(ctx.concept_doc_freq.get(parent, 0))
    child_df = float(ctx.concept_doc_freq.get(child, 0))
    lexical = max(
        _token_jaccard(parent, child),
        _evidence_value(edge, "lexical_similarity"),
    )
    semantic = max(
        _evidence_value(edge, "semantic_similarity"),
        _evidence_value(edge, "cosine_similarity"),
        _evidence_value(edge, "similarity"),
    )
    cooc = float(cooc_support.get((parent, child), 0.0))
    parent_validity = parent_validity_score(parent, ctx.concept_doc_freq)
    return {
        "method": method,
        "lang": _infer_edge_lang(ctx, parent, child),
        "base_score": float(edge.get("score", 0.0)),
        "semantic_similarity": round(semantic, 6),
        "lexical_similarity": round(lexical, 6),
        "cooccurrence_support": round(cooc, 6),
        "parent_validity": round(parent_validity, 6),
        "parent_doc_freq": round(parent_df, 6),
        "child_doc_freq": round(child_df, 6),
        "df_gap": round(parent_df - child_df, 6),
        "token_len_gap": float(len(tokenize(parent)) - len(tokenize(child))),
        "projected_parent_outdegree": float(parent_degree.get(parent, 0)),
    }


def predict_ranker_score(ctx: BuildContext, features: dict[str, float | str]) -> float | None:
    if not ctx.settings.edge_ranker_enabled or ctx.ranker is None:
        return None
    try:
        model = ctx.ranker
        model_obj = model
        names = None
        if isinstance(model, dict):
            model_obj = model.get("model")
            names = list(model.get("feature_name_") or [])
        if not names and hasattr(model_obj, "feature_name_"):
            names = list(getattr(model_obj, "feature_name_"))
        elif not names and hasattr(model_obj, "feature_names_in_"):
            names = list(getattr(model_obj, "feature_names_in_"))
        else:
            names = sorted(k for k, v in features.items() if isinstance(v, (int, float)))
        vector = [[float(features.get(name, 0.0) or 0.0) for name in names]]
        if hasattr(model_obj, "predict_proba"):
            proba = model_obj.predict_proba(vector)
            if proba is not None and len(proba) > 0:
                return float(proba[0][-1])
        pred = model_obj.predict(vector)
        if pred is not None and len(pred) > 0:
            return float(pred[0])
    except Exception:
        return None
    return None


def _risk_score(features: dict[str, float | str], final_score: float, rejected_reason: str | None) -> float:
    uncertainty = 1.0 - abs((2.0 * final_score) - 1.0)
    parent_validity = float(features.get("parent_validity", 0.0) or 0.0)
    lexical = float(features.get("lexical_similarity", 0.0) or 0.0)
    df_gap = float(features.get("df_gap", 0.0) or 0.0)
    inversion = 1.0 if df_gap < -1.0 else 0.0
    risk = (0.35 * uncertainty) + (0.25 * max(0.0, 0.55 - parent_validity)) + (0.20 * (1.0 - lexical)) + (0.20 * inversion)
    if rejected_reason:
        risk += 0.10
    return max(0.0, min(1.0, risk))


def build_candidate_log(
    ctx: BuildContext,
    edge: dict,
    features: dict[str, float | str],
    decision: str,
    rejection_reason: str | None,
    min_score: float,
    ranker_score: float | None,
    evidence_score: float | None,
    stage: str = "initial_filter",
) -> dict:
    parent = ctx.concept_map.get(edge["hypernym"])
    child = ctx.concept_map.get(edge["hyponym"])
    final_score = float(edge.get("score", 0.0))
    risk = _risk_score(features, final_score, rejection_reason)
    return {
        "taxonomy_version_id": ctx.taxonomy_version_id,
        "collection_id": ctx.collection_id,
        "parent_concept_id": str(parent.id) if parent else None,
        "child_concept_id": str(child.id) if child else None,
        "parent_label": edge["hypernym"],
        "child_label": edge["hyponym"],
        "lang": str(features.get("lang", "unknown")),
        "method": str(features.get("method", "unknown")),
        "stage": stage,
        "base_score": float(features.get("base_score", 0.0) or 0.0),
        "ranker_score": ranker_score,
        "evidence_score": evidence_score,
        "final_score": final_score,
        "decision": decision,
        "risk_score": risk,
        "rejection_reason": rejection_reason,
        "feature_vector": dict(features),
        "evidence": edge.get("evidence", {}),
        "min_score": min_score,
    }


def build_all_relation_candidates(ctx: BuildContext) -> list[dict]:
    all_pairs: list[dict] = []
    concept_set = set(ctx.concept_labels)
    if ctx.method in ("hearst", "hybrid"):
        hearst_pairs: list[dict] = []
        hearst_soft_pairs: list[dict] = []
        hearst_trigger_pairs: list[dict] = []
        for lang, group_chunks in ctx.lang_groups.items():
            lang_hard = extract_hearst_pairs(group_chunks, concept_set, lang, soft_mode=False)
            hearst_pairs.extend(lang_hard)
            lang_soft: list[dict] = []
            if ctx.settings.hearst_soft_mode:
                lang_soft = extract_hearst_pairs(group_chunks, concept_set, lang, soft_mode=True)
                hearst_soft_pairs.extend(lang_soft)
            if ctx.settings.hearst_trigger_fallback_enabled:
                hard_min_expected = max(4, len(ctx.concepts) // 25)
                current_lang_hearst = len(lang_hard) + len(lang_soft)
                if current_lang_hearst < hard_min_expected:
                    hearst_trigger_pairs.extend(
                        extract_hearst_trigger_pairs(
                            group_chunks,
                            concept_set,
                            lang=lang,
                            concept_doc_freq=ctx.concept_doc_freq,
                            max_pairs=max(6, ctx.settings.hearst_trigger_fallback_max_pairs // max(1, len(ctx.lang_groups))),
                        )
                    )
        if hearst_soft_pairs:
            hearst_pairs.extend(hearst_soft_pairs)
        if hearst_trigger_pairs:
            hearst_pairs.extend(hearst_trigger_pairs)
        all_pairs.extend(hearst_pairs)
        add_job_event(
            ctx.session,
            ctx.job_id,
            "INFO",
            f"Hearst patterns found {len(hearst_pairs)} relations across langs={ctx.lang_counts} "
            f"(soft_mode={ctx.settings.hearst_soft_mode}, trigger_fallback={len(hearst_trigger_pairs)})",
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
    cooc_support = compute_pair_cooccurrence(ctx.chunks, ctx.concept_labels)
    parent_degree: dict[str, int] = {}
    for edge in unique_pairs:
        parent_degree[edge["hypernym"]] = parent_degree.get(edge["hypernym"], 0) + 1

    accepted_pairs: list[dict] = []
    candidate_logs: list[dict] = []
    rejected = 0
    for edge in unique_pairs:
        method = edge_method(edge)
        features = extract_edge_features(ctx, edge, cooc_support, parent_degree)
        default_min_score = edge_min_score(edge, min_edge_accept_score, method_thresholds)
        if ctx.settings.adaptive_thresholds_enabled:
            prof_min = threshold_from_profile(
                ctx.threshold_profile,
                method=method,
                lang=str(features.get("lang", "")),
                fallback=default_min_score,
            )
            method_thresholds[method] = prof_min
            min_score = float(prof_min)
        else:
            min_score = default_min_score

        base = float(edge.get("score", 0.0))
        cooc = float(features["cooccurrence_support"])
        method_w = method_weight(method)
        parent_validity = float(features["parent_validity"])
        evidence_score = (
            (0.65 * float(features["semantic_similarity"]))
            + (0.25 * float(features["lexical_similarity"]))
            + (0.10 * cooc)
        )
        composite = max(0.0, min(1.0, (method_w * base) + (0.20 * cooc) + (0.18 * parent_validity)))
        ranker_score = predict_ranker_score(ctx, features)
        if ranker_score is not None and ranker_score < ctx.settings.edge_ranker_min_confidence:
            ranker_score = None
        final_score = blend_scores(
            base_score=composite,
            ranker_score=ranker_score,
            evidence_score=evidence_score if ctx.settings.evidence_linking_enabled else None,
            ranker_alpha=ctx.settings.edge_ranker_blend_alpha,
            evidence_alpha=0.12,
        )
        edge["score"] = round(final_score, 4)
        ev = edge.get("evidence", {})
        if isinstance(ev, dict):
            ev["semantic_similarity"] = round(float(features["semantic_similarity"]), 4)
            ev["lexical_similarity"] = round(float(features["lexical_similarity"]), 4)
            ev["cooccurrence_support"] = round(cooc, 4)
            ev["parent_validity"] = round(parent_validity, 4)
            ev["composite_score"] = round(composite, 4)
            if ranker_score is not None:
                ev["ranker_score"] = round(ranker_score, 4)
            if ctx.settings.evidence_linking_enabled:
                ev["evidence_score"] = round(evidence_score, 4)
            edge["evidence"] = ev

        reason = edge_rejection_reason(edge, ctx.concept_doc_freq, min_score)
        if reason is None:
            accepted_pairs.append(edge)
            candidate_logs.append(
                build_candidate_log(
                    ctx,
                    edge,
                    features,
                    decision="accepted",
                    rejection_reason=None,
                    min_score=min_score,
                    ranker_score=ranker_score,
                    evidence_score=evidence_score if ctx.settings.evidence_linking_enabled else None,
                )
            )
        else:
            rejected += 1
            candidate_logs.append(
                build_candidate_log(
                    ctx,
                    edge,
                    features,
                    decision="rejected",
                    rejection_reason=reason,
                    min_score=min_score,
                    ranker_score=ranker_score,
                    evidence_score=evidence_score if ctx.settings.evidence_linking_enabled else None,
                )
            )

    unique_pairs = accepted_pairs
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        f"Adaptive edge accept thresholds: default={min_edge_accept_score:.2f}, "
        f"per_method={method_thresholds}, accepted={len(unique_pairs)}, rejected={rejected}, "
        f"profile_id={ctx.threshold_profile_id or 'none'}, ranker={str(ctx.ranker is not None).lower()}",
    )

    return BuildState(
        unique_pairs=unique_pairs,
        connectivity_candidate_pool=[],
        min_edge_accept_score=min_edge_accept_score,
        method_thresholds=method_thresholds,
        candidate_logs=candidate_logs,
        ranker_enabled=ctx.settings.edge_ranker_enabled and ctx.ranker is not None,
    )
