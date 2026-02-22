from __future__ import annotations

import uuid

from app.db import TaxonomyEdge
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
