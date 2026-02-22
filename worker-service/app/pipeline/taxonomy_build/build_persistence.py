from __future__ import annotations

import uuid

from app.db import TaxonomyEdge, TaxonomyEdgeCandidate
from app.job_helper import add_job_event, update_job_status, update_taxonomy_status
from app.logger import get_logger
from app.pipeline.taxonomy_build.build_types import BuildContext

log = get_logger(__name__)


def persist_taxonomy_edges(ctx: BuildContext, unique_pairs: list[dict]) -> int:
    ctx.session.query(TaxonomyEdge).filter(
        TaxonomyEdge.taxonomy_version_id == ctx.taxonomy_version_id
    ).delete()
    ctx.session.commit()

    stored = 0
    for pair in unique_pairs:
        parent = ctx.concept_map.get(pair["hypernym"])
        child = ctx.concept_map.get(pair["hyponym"])
        if not parent or not child:
            continue
        edge = TaxonomyEdge(
            id=uuid.uuid4(),
            taxonomy_version_id=ctx.taxonomy_version_id,
            parent_concept_id=parent.id,
            child_concept_id=child.id,
            relation="is_a",
            score=pair["score"],
            evidence=[pair["evidence"]] if isinstance(pair["evidence"], dict) else pair["evidence"],
        )
        ctx.session.add(edge)
        stored += 1
        if stored % 100 == 0:
            ctx.session.commit()
    ctx.session.commit()
    return stored


def persist_edge_candidates(ctx: BuildContext, candidate_logs: list[dict]) -> int:
    if not candidate_logs:
        return 0
    logs = list(candidate_logs)
    if ctx.settings.active_learning_enabled and len(logs) > ctx.settings.active_learning_batch_size:
        logs = sorted(logs, key=lambda x: float(x.get("risk_score", 0.0)), reverse=True)[
            : ctx.settings.active_learning_batch_size
        ]

    stored = 0
    for item in logs:
        parent_concept_id = item.get("parent_concept_id")
        child_concept_id = item.get("child_concept_id")
        if isinstance(parent_concept_id, str):
            try:
                parent_concept_id = uuid.UUID(parent_concept_id)
            except ValueError:
                parent_concept_id = None
        if isinstance(child_concept_id, str):
            try:
                child_concept_id = uuid.UUID(child_concept_id)
            except ValueError:
                child_concept_id = None
        feature_vector = dict(item.get("feature_vector") or {})
        if "min_score" in item:
            feature_vector["min_score"] = float(item.get("min_score", 0.0))
        row = TaxonomyEdgeCandidate(
            id=uuid.uuid4(),
            taxonomy_version_id=ctx.taxonomy_version_id,
            collection_id=ctx.collection_id,
            parent_concept_id=parent_concept_id,
            child_concept_id=child_concept_id,
            parent_label=item.get("parent_label", ""),
            child_label=item.get("child_label", ""),
            lang=item.get("lang"),
            method=item.get("method", "unknown"),
            stage=item.get("stage", "build"),
            base_score=float(item.get("base_score", 0.0) or 0.0),
            ranker_score=item.get("ranker_score"),
            evidence_score=item.get("evidence_score"),
            final_score=float(item.get("final_score", 0.0) or 0.0),
            decision=item.get("decision", "pending"),
            risk_score=float(item.get("risk_score", 0.0) or 0.0),
            rejection_reason=item.get("rejection_reason"),
            feature_vector=feature_vector,
            evidence=item.get("evidence", {}),
        )
        ctx.session.add(row)
        stored += 1
        if stored % 250 == 0:
            ctx.session.commit()
    ctx.session.commit()
    return stored


def finalize_success(ctx: BuildContext, stored: int) -> None:
    update_taxonomy_status(ctx.session, ctx.taxonomy_version_id, "READY")
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        f"Taxonomy build complete: {stored} edges, method={ctx.method}",
    )
    update_job_status(ctx.session, ctx.job_id, "RUNNING", progress=100)
    log.info(
        "Taxonomy build complete: collection=%s version=%s edges=%d",
        ctx.collection_id,
        ctx.taxonomy_version_id,
        stored,
    )


def finalize_empty(ctx: BuildContext, message: str) -> None:
    add_job_event(ctx.session, ctx.job_id, "WARN", message)
    update_taxonomy_status(ctx.session, ctx.taxonomy_version_id, "READY")
    update_job_status(ctx.session, ctx.job_id, "RUNNING", progress=100)
