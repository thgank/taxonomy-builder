"""
Evaluation worker
─────────────────
Computes quality metrics for a built taxonomy:
  - Structural metrics (depth, branching factor, coverage)
  - Edge confidence statistics
  - Orphan / isolated concept detection

Results stored in taxonomy_versions.quality_metrics (JSONB).
"""
from __future__ import annotations

import uuid
import math
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.config import config
from app.db import (
    Concept, TaxonomyEdge, TaxonomyVersion, Document, DocumentChunk,
)
from app.job_helper import (
    update_job_status, add_job_event, update_taxonomy_status, is_job_cancelled,
)
from app.logger import get_logger

log = get_logger(__name__)


def _compute_structural_metrics(
    concepts: list[Concept],
    edges: list[TaxonomyEdge],
) -> dict[str, Any]:
    """Compute structural quality metrics for the taxonomy tree."""
    if not concepts:
        return {"error": "no_concepts"}

    total_concepts = len(concepts)
    total_edges = len(edges)

    # Build adjacency
    parent_to_children: dict[str, list[str]] = defaultdict(list)
    child_to_parents: dict[str, set] = defaultdict(set)
    concept_ids_in_edges: set[str] = set()

    for e in edges:
        pid = str(e.parent_concept_id)
        cid = str(e.child_concept_id)
        parent_to_children[pid].append(cid)
        child_to_parents[cid].add(pid)
        concept_ids_in_edges.add(pid)
        concept_ids_in_edges.add(cid)

    all_concept_ids = {str(c.id) for c in concepts}

    # Roots: parents that are not children
    roots = set(parent_to_children.keys()) - set(child_to_parents.keys())
    # Leaves: children that are not parents
    leaves = set(child_to_parents.keys()) - set(parent_to_children.keys())
    # Orphans: concepts not in any edge
    orphans = all_concept_ids - concept_ids_in_edges

    # Compute depth via BFS from roots
    depths: dict[str, int] = {}
    queue = list(roots)
    for r in roots:
        depths[r] = 0
    while queue:
        node = queue.pop(0)
        for child in parent_to_children.get(node, []):
            if child not in depths:
                depths[child] = depths[node] + 1
                queue.append(child)

    max_depth = max(depths.values()) if depths else 0
    avg_depth = sum(depths.values()) / len(depths) if depths else 0.0

    # Branching factor
    branching_factors = [len(children) for children in parent_to_children.values()]
    avg_branching = (
        sum(branching_factors) / len(branching_factors)
        if branching_factors else 0.0
    )
    max_branching = max(branching_factors) if branching_factors else 0

    # Coverage: fraction of concepts that appear in at least one edge
    coverage = len(concept_ids_in_edges) / total_concepts if total_concepts > 0 else 0.0

    return {
        "total_concepts": total_concepts,
        "total_edges": total_edges,
        "root_count": len(roots),
        "leaf_count": len(leaves),
        "orphan_count": len(orphans),
        "max_depth": max_depth,
        "avg_depth": round(avg_depth, 2),
        "avg_branching_factor": round(avg_branching, 2),
        "max_branching_factor": max_branching,
        "coverage": round(coverage, 4),
    }


def _compute_edge_confidence_stats(edges: list[TaxonomyEdge]) -> dict[str, Any]:
    """Compute statistics on edge confidence scores."""
    if not edges:
        return {"count": 0}

    scores = [e.score for e in edges if e.score is not None]
    if not scores:
        return {"count": len(edges), "scored": 0}

    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)

    # Standard deviation
    if len(scores) > 1:
        variance = sum((s - avg_score) ** 2 for s in scores) / (len(scores) - 1)
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.0

    # Score distribution buckets
    buckets = {"0.0-0.3": 0, "0.3-0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0}
    for s in scores:
        if s < 0.3:
            buckets["0.0-0.3"] += 1
        elif s < 0.5:
            buckets["0.3-0.5"] += 1
        elif s < 0.7:
            buckets["0.5-0.7"] += 1
        elif s < 0.9:
            buckets["0.7-0.9"] += 1
        else:
            buckets["0.9-1.0"] += 1

    # Method distribution
    method_counts: dict[str, int] = defaultdict(int)
    for e in edges:
        if isinstance(e.evidence, list):
            for ev in e.evidence:
                if isinstance(ev, dict):
                    method_counts[ev.get("method", "unknown")] += 1

    return {
        "count": len(edges),
        "scored": len(scores),
        "avg_score": round(avg_score, 4),
        "min_score": round(min_score, 4),
        "max_score": round(max_score, 4),
        "std_dev": round(std_dev, 4),
        "score_distribution": buckets,
        "method_distribution": dict(method_counts),
    }


def handle_evaluate(session: Session, msg: dict) -> None:
    """Evaluation handler: compute quality metrics and store on taxonomy version."""
    job_id = str(msg.get("jobId") or msg.get("job_id"))
    collection_id = str(msg.get("collectionId") or msg.get("collection_id"))
    taxonomy_version_id = str(
        msg.get("taxonomyVersionId") or msg.get("taxonomy_version_id")
    )
    params = msg.get("params", {})

    update_job_status(session, job_id, "RUNNING", progress=0)
    add_job_event(session, job_id, "INFO", "Evaluation started")

    # ── Load data ────────────────────────────────────────
    concepts = (
        session.query(Concept)
        .filter(Concept.collection_id == collection_id)
        .all()
    )
    edges = (
        session.query(TaxonomyEdge)
        .filter(TaxonomyEdge.taxonomy_version_id == taxonomy_version_id)
        .all()
    )

    if is_job_cancelled(session, job_id):
        return

    update_job_status(session, job_id, "RUNNING", progress=20)

    # ── Structural metrics ───────────────────────────────
    structural = _compute_structural_metrics(concepts, edges)
    add_job_event(
        session, job_id, "INFO",
        f"Structural metrics: {structural.get('total_edges', 0)} edges, "
        f"depth={structural.get('max_depth', 0)}, "
        f"coverage={structural.get('coverage', 0):.1%}",
    )
    update_job_status(session, job_id, "RUNNING", progress=50)

    # ── Edge confidence stats ────────────────────────────
    edge_stats = _compute_edge_confidence_stats(edges)
    add_job_event(
        session, job_id, "INFO",
        f"Edge confidence: avg={edge_stats.get('avg_score', 0):.3f}, "
        f"std={edge_stats.get('std_dev', 0):.3f}",
    )
    update_job_status(session, job_id, "RUNNING", progress=75)

    # ── Compose quality report ───────────────────────────
    quality_metrics = {
        "structural": structural,
        "edge_confidence": edge_stats,
    }

    # ── Store on taxonomy version ────────────────────────
    tv = session.query(TaxonomyVersion).filter(
        TaxonomyVersion.id == taxonomy_version_id
    ).first()
    if tv:
        tv.quality_metrics = quality_metrics
        tv.status = "READY"
        session.commit()

    update_job_status(session, job_id, "RUNNING", progress=100)
    add_job_event(
        session, job_id, "INFO",
        f"Evaluation complete: coverage={structural.get('coverage', 0):.1%}, "
        f"edges={structural.get('total_edges', 0)}, "
        f"avg_confidence={edge_stats.get('avg_score', 0):.3f}",
    )

    log.info(
        "Evaluation complete for taxonomy %s: %d concepts, %d edges, coverage=%.1f%%",
        taxonomy_version_id,
        structural.get("total_concepts", 0),
        structural.get("total_edges", 0),
        structural.get("coverage", 0) * 100,
    )
