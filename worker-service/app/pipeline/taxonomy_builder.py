"""
Taxonomy Builder handler.
Orchestrates Hearst + embedding methods, post-processing, quality gates, and DB writes.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.job_helper import (
    add_job_event,
    is_job_cancelled,
    update_job_status,
    update_taxonomy_status,
)
from app.pipeline.taxonomy_build.build_context import load_build_context
from app.pipeline.taxonomy_build.build_expansion import apply_connectivity_expansion
from app.pipeline.taxonomy_build.build_generation import build_all_relation_candidates, build_initial_state
from app.pipeline.taxonomy_build.build_persistence import (
    finalize_empty,
    finalize_success,
    persist_edge_candidates,
    persist_taxonomy_edges,
)
from app.pipeline.taxonomy_build.build_recovery_quality import (
    evaluate_quality_gate_and_hubness,
    run_postprocess_and_recovery,
)


def handle_build(session: Session, msg: dict) -> None:
    """Build taxonomy hierarchy."""
    job_id = str(msg.get("jobId") or msg.get("job_id"))
    collection_id = str(msg.get("collectionId") or msg.get("collection_id"))
    taxonomy_version_id = str(msg.get("taxonomyVersionId") or msg.get("taxonomy_version_id"))
    params = msg.get("params", {})

    update_job_status(session, job_id, "RUNNING", progress=0)
    update_taxonomy_status(session, taxonomy_version_id, "RUNNING")
    add_job_event(session, job_id, "INFO", "Taxonomy build started")

    ctx = load_build_context(session, job_id, collection_id, taxonomy_version_id, params)
    if not ctx.concepts:
        finalize_empty(ctx, "No concepts found — skipping build")
        return

    all_pairs = build_all_relation_candidates(ctx)
    if is_job_cancelled(session, job_id):
        return
    if not all_pairs:
        finalize_empty(ctx, "No taxonomy relations found")
        return

    state = build_initial_state(ctx, all_pairs)
    apply_connectivity_expansion(ctx, state)
    run_postprocess_and_recovery(ctx, state)
    candidate_logs_stored = persist_edge_candidates(ctx, state.candidate_logs)
    add_job_event(
        ctx.session,
        ctx.job_id,
        "INFO",
        f"Candidate edge logs persisted: {candidate_logs_stored}, "
        f"threshold_profile={ctx.threshold_profile_id or 'none'}, "
        f"ranker_enabled={str(state.ranker_enabled).lower()}",
    )

    _, violations = evaluate_quality_gate_and_hubness(ctx, state)
    if violations:
        add_job_event(ctx.session, ctx.job_id, "WARN", "Quality gate violations: " + "; ".join(violations))
        if ctx.settings.enforce_quality_gate:
            update_taxonomy_status(ctx.session, ctx.taxonomy_version_id, "FAILED")
            update_job_status(
                ctx.session,
                ctx.job_id,
                "FAILED",
                progress=100,
                error_message="Quality gate failed: " + "; ".join(violations),
            )
            return

    add_job_event(ctx.session, ctx.job_id, "INFO", f"After post-processing: {len(state.unique_pairs)} edges")
    update_job_status(ctx.session, ctx.job_id, "RUNNING", progress=80)

    stored = persist_taxonomy_edges(ctx, state.unique_pairs)
    finalize_success(ctx, stored)
