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
    Concept, ConceptOccurrence, TaxonomyEdge, TaxonomyVersion, Document, DocumentChunk,
    TaxonomyEdgeCandidate, TaxonomyEdgeLabel,
)
from app.job_helper import (
    update_job_status, add_job_event, update_taxonomy_status, is_job_cancelled,
)
from app.logger import get_logger
from app.pipeline.taxonomy_quality import compute_graph_quality
from app.pipeline.taxonomy_text import is_low_quality_label, tokenize

log = get_logger(__name__)


def _compute_structural_metrics(
    concepts: list[Concept],
    edges: list[TaxonomyEdge],
    candidate_concept_ids: set[str] | None = None,
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
    high_quality_concepts = [
        c for c in concepts
        if not is_low_quality_label(c.canonical)
    ]
    high_quality_ids = {str(c.id) for c in high_quality_concepts}
    high_quality_connected = high_quality_ids & concept_ids_in_edges
    coverage_high_quality = (
        len(high_quality_connected) / len(high_quality_ids)
        if high_quality_ids else 0.0
    )
    if candidate_concept_ids is None:
        candidate_concept_ids = high_quality_ids
    candidate_connected = concept_ids_in_edges & candidate_concept_ids
    coverage_candidate_set = (
        len(candidate_connected) / len(candidate_concept_ids)
        if candidate_concept_ids else 0.0
    )
    by_lang: dict[str, dict[str, Any]] = {}
    for lang in sorted({(c.lang or "unknown") for c in concepts}):
        lang_concepts = [c for c in concepts if (c.lang or "unknown") == lang]
        lang_ids = {str(c.id) for c in lang_concepts}
        if not lang_ids:
            continue
        connected = concept_ids_in_edges & lang_ids
        by_lang[lang] = {
            "concepts": len(lang_ids),
            "connected": len(connected),
            "coverage": round(len(connected) / len(lang_ids), 4),
        }

    return {
        "total_concepts": total_concepts,
        "high_quality_concepts": len(high_quality_ids),
        "candidate_concepts": len(candidate_concept_ids),
        "total_edges": total_edges,
        "root_count": len(roots),
        "leaf_count": len(leaves),
        "orphan_count": len(orphans),
        "max_depth": max_depth,
        "avg_depth": round(avg_depth, 2),
        "avg_branching_factor": round(avg_branching, 2),
        "max_branching_factor": max_branching,
        "coverage": round(coverage, 4),
        "coverage_high_quality": round(coverage_high_quality, 4),
        "coverage_candidate_set": round(coverage_candidate_set, 4),
        "by_language": by_lang,
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


def _compute_graph_connectivity_metrics(
    concepts: list[Concept],
    edges: list[TaxonomyEdge],
    candidate_concept_ids: set[str],
) -> dict[str, Any]:
    concept_by_id = {str(c.id): c for c in concepts}
    resolved_edges: list[tuple[str, str, str, str]] = []
    for e in edges:
        pid = str(e.parent_concept_id)
        cid = str(e.child_concept_id)
        parent = concept_by_id.get(pid)
        child = concept_by_id.get(cid)
        if not parent or not child:
            continue
        resolved_edges.append((pid, cid, parent.canonical, child.canonical))

    edge_dicts_all = [{"hypernym": p_lbl, "hyponym": c_lbl} for _pid, _cid, p_lbl, c_lbl in resolved_edges]
    edge_dicts_candidate = [
        {"hypernym": p_lbl, "hyponym": c_lbl}
        for pid, cid, p_lbl, c_lbl in resolved_edges
        if pid in candidate_concept_ids and cid in candidate_concept_ids
    ]

    all_report = compute_graph_quality(edge_dicts_all, len(concepts))
    candidate_report = compute_graph_quality(edge_dicts_candidate, len(candidate_concept_ids))
    by_language: dict[str, Any] = {}
    for lang in sorted({(c.lang or "unknown") for c in concepts}):
        lang_ids = {str(c.id) for c in concepts if (c.lang or "unknown") == lang}
        lang_candidate_ids = lang_ids & candidate_concept_ids
        lang_edges_all = [
            {"hypernym": p_lbl, "hyponym": c_lbl}
            for pid, cid, p_lbl, c_lbl in resolved_edges
            if pid in lang_ids and cid in lang_ids
        ]
        lang_edges_candidate = [
            {"hypernym": p_lbl, "hyponym": c_lbl}
            for pid, cid, p_lbl, c_lbl in resolved_edges
            if pid in lang_candidate_ids and cid in lang_candidate_ids
        ]
        by_language[lang] = {
            "all_concepts": {
                "denominator": len(lang_ids),
                "edge_count": len(lang_edges_all),
                **compute_graph_quality(lang_edges_all, len(lang_ids)),
            },
            "candidate_concepts": {
                "denominator": len(lang_candidate_ids),
                "edge_count": len(lang_edges_candidate),
                **compute_graph_quality(lang_edges_candidate, len(lang_candidate_ids)),
            },
        }
    return {
        "all_concepts": {
            "denominator": len(concepts),
            **all_report,
        },
        "candidate_concepts": {
            "denominator": len(candidate_concept_ids),
            **candidate_report,
        },
        "by_language": by_language,
    }


def _compute_fragmentation_and_risk_metrics(
    concepts: list[Concept],
    edges: list[TaxonomyEdge],
    concept_doc_sets: dict[str, set[str]],
) -> dict[str, Any]:
    concept_by_id = {str(c.id): c for c in concepts}
    node_ids = set(concept_by_id.keys())
    adjacency: dict[str, set[str]] = defaultdict(set)
    for node_id in node_ids:
        adjacency.setdefault(node_id, set())
    low_score_threshold = float(config.orientation_sanity_low_score_threshold)
    low_score_edges = 0
    orientation_risk_count = 0
    orientation_risk_examples: list[dict[str, Any]] = []
    for edge in edges:
        pid = str(edge.parent_concept_id)
        cid = str(edge.child_concept_id)
        if pid not in concept_by_id or cid not in concept_by_id:
            continue
        adjacency[pid].add(cid)
        adjacency[cid].add(pid)
        score = float(edge.score or 0.0)
        if score <= low_score_threshold:
            low_score_edges += 1
            parent_label = concept_by_id[pid].canonical
            child_label = concept_by_id[cid].canonical
            p_tokens = tokenize(parent_label)
            c_tokens = tokenize(child_label)
            p_df = len(concept_doc_sets.get(pid, set()))
            c_df = len(concept_doc_sets.get(cid, set()))
            lexical_subset = (
                len(p_tokens) > len(c_tokens) and len(c_tokens) > 0 and set(c_tokens).issubset(set(p_tokens))
            )
            child_more_general = c_df >= (p_df + 2) and len(c_tokens) <= len(p_tokens)
            if lexical_subset or child_more_general:
                orientation_risk_count += 1
                if len(orientation_risk_examples) < 12:
                    orientation_risk_examples.append(
                        {
                            "parent": parent_label,
                            "child": child_label,
                            "score": round(score, 4),
                            "lexical_subset": lexical_subset,
                            "doc_freq_parent": p_df,
                            "doc_freq_child": c_df,
                        }
                    )

    visited: set[str] = set()
    components: list[int] = []
    for node in node_ids:
        if node in visited:
            continue
        stack = [node]
        size = 0
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            size += 1
            stack.extend(adjacency[cur] - visited)
        components.append(size)

    components.sort(reverse=True)
    total_nodes = len(node_ids)
    small_components = sum(1 for s in components if s <= 2)
    isolated_components = sum(1 for s in components if s == 1)
    small_component_nodes = sum(s for s in components if s <= 2)
    return {
        "component_count": len(components),
        "largest_component_size": components[0] if components else 0,
        "small_components_count": small_components,
        "isolated_components_count": isolated_components,
        "fragmentation_index": round(len(components) / max(1, total_nodes), 4),
        "small_component_node_ratio": round(small_component_nodes / max(1, total_nodes), 4),
        "low_score_threshold": round(low_score_threshold, 4),
        "low_score_edge_count": low_score_edges,
        "low_score_edge_ratio": round(low_score_edges / max(1, len(edges)), 4),
        "orientation_risk_count": orientation_risk_count,
        "orientation_risk_ratio": round(orientation_risk_count / max(1, len(edges)), 4),
        "orientation_risk_examples": orientation_risk_examples,
    }


def _compute_manual_review_metrics(edges: list[TaxonomyEdge]) -> dict[str, Any]:
    reviewed = 0
    disagreed = 0
    approved = 0
    for edge in edges:
        if edge.approved is None:
            continue
        reviewed += 1
        if bool(edge.approved):
            approved += 1
        else:
            disagreed += 1
    disagreement_rate = (disagreed / reviewed) if reviewed else 0.0
    approval_rate = (approved / reviewed) if reviewed else 0.0
    return {
        "reviewed_edges": reviewed,
        "approved_edges": approved,
        "rejected_edges": disagreed,
        "manual_disagreement_rate": round(disagreement_rate, 4),
        "manual_approval_rate": round(approval_rate, 4),
    }


def _compute_cross_lang_consistency(
    concepts: list[Concept],
    edges: list[TaxonomyEdge],
) -> dict[str, Any]:
    concept_by_id = {str(c.id): c for c in concepts}

    def _anchor(label: str) -> str:
        tokens = tokenize(label or "")
        return " ".join(tokens[:4])

    edge_lang_map: dict[tuple[str, str], set[str]] = defaultdict(set)
    comparable_pairs = 0
    consistent_pairs = 0
    sample_conflicts: list[dict[str, Any]] = []
    for edge in edges:
        parent = concept_by_id.get(str(edge.parent_concept_id))
        child = concept_by_id.get(str(edge.child_concept_id))
        if not parent or not child:
            continue
        p_anchor = _anchor(parent.canonical)
        c_anchor = _anchor(child.canonical)
        if not p_anchor or not c_anchor:
            continue
        if p_anchor == c_anchor:
            continue
        lang = ((parent.lang or child.lang or "unknown").lower()[:2])
        edge_lang_map[(p_anchor, c_anchor)].add(lang)

    inverse_map = {k: (k[1], k[0]) for k in edge_lang_map.keys()}
    for pair, langs in edge_lang_map.items():
        inv_pair = inverse_map.get(pair)
        inv_langs = edge_lang_map.get(inv_pair, set()) if inv_pair else set()
        union_langs = langs | inv_langs
        if len(union_langs) < 2:
            continue
        comparable_pairs += 1
        if len(inv_langs) == 0:
            consistent_pairs += 1
        elif len(sample_conflicts) < 10:
            sample_conflicts.append(
                {
                    "pair": {"parent_anchor": pair[0], "child_anchor": pair[1]},
                    "langs_forward": sorted(langs),
                    "langs_reverse": sorted(inv_langs),
                }
            )

    consistency = (consistent_pairs / comparable_pairs) if comparable_pairs else 1.0
    return {
        "comparable_pairs": comparable_pairs,
        "consistent_pairs": consistent_pairs,
        "cross_lang_consistency": round(consistency, 4),
        "cross_lang_consistency_target": round(float(config.cross_lang_consistency_min), 4),
        "meets_target": consistency >= float(config.cross_lang_consistency_min),
        "sample_conflicts": sample_conflicts,
    }


def _compute_quality_score_10(
    structural: dict[str, Any],
    graph_connectivity: dict[str, Any],
    risk: dict[str, Any],
    manual_review: dict[str, Any],
) -> float:
    coverage_candidate = float(structural.get("coverage_candidate_set", 0.0) or 0.0)
    lcr = float((graph_connectivity.get("all_concepts") or {}).get("largest_component_ratio", 0.0) or 0.0)
    hubness = float((graph_connectivity.get("all_concepts") or {}).get("hubness", 0.0) or 0.0)
    fragmentation = float(risk.get("fragmentation_index", 1.0) or 1.0)
    low_score_tail = float(risk.get("low_score_edge_ratio", 1.0) or 1.0)
    disagreement = float(manual_review.get("manual_disagreement_rate", 0.0) or 0.0)

    hubness_penalty = min(1.0, max(0.0, hubness / 8.0))
    score = (
        0.30 * coverage_candidate
        + 0.25 * lcr
        + 0.15 * (1.0 - min(1.0, fragmentation))
        + 0.10 * (1.0 - min(1.0, low_score_tail))
        + 0.10 * (1.0 - hubness_penalty)
        + 0.10 * (1.0 - min(1.0, disagreement))
    )
    return round(max(0.0, min(10.0, 10.0 * score)), 3)


def _compute_active_learning_metrics(
    session: Session,
    taxonomy_version_id: str,
    collection_id: str,
) -> dict[str, Any]:
    top_risk = (
        session.query(TaxonomyEdgeCandidate)
        .filter(TaxonomyEdgeCandidate.taxonomy_version_id == taxonomy_version_id)
        .order_by(TaxonomyEdgeCandidate.risk_score.desc())
        .limit(25)
        .all()
    )
    label_count = (
        session.query(TaxonomyEdgeLabel)
        .filter(TaxonomyEdgeLabel.collection_id == collection_id)
        .count()
    )
    accepted = sum(1 for row in top_risk if (row.decision or "") == "accepted")
    rejected = sum(1 for row in top_risk if (row.decision or "") == "rejected")
    return {
        "top_risk_candidates": [
            {
                "parent": row.parent_label,
                "child": row.child_label,
                "method": row.method,
                "risk_score": round(float(row.risk_score or 0.0), 4),
                "decision": row.decision,
            }
            for row in top_risk[:12]
        ],
        "top_risk_count": len(top_risk),
        "top_risk_accepted": accepted,
        "top_risk_rejected": rejected,
        "historical_label_count": int(label_count),
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
    concept_ids = [c.id for c in concepts]
    doc_rows = (
        session.query(ConceptOccurrence.concept_id, DocumentChunk.document_id)
        .join(DocumentChunk, ConceptOccurrence.chunk_id == DocumentChunk.id)
        .filter(ConceptOccurrence.concept_id.in_(concept_ids))
        .all()
    )
    concept_doc_sets: dict[str, set[str]] = defaultdict(set)
    for concept_id, document_id in doc_rows:
        concept_doc_sets[str(concept_id)].add(str(document_id))
    candidate_concept_ids = {
        str(c.id)
        for c in concepts
        if not is_low_quality_label(c.canonical) and len(concept_doc_sets.get(str(c.id), set())) >= 2
    }

    if is_job_cancelled(session, job_id):
        return

    update_job_status(session, job_id, "RUNNING", progress=20)

    # ── Structural metrics ───────────────────────────────
    structural = _compute_structural_metrics(
        concepts,
        edges,
        candidate_concept_ids=candidate_concept_ids,
    )
    add_job_event(
        session, job_id, "INFO",
        f"Structural metrics: {structural.get('total_edges', 0)} edges, "
        f"depth={structural.get('max_depth', 0)}, "
        f"coverage={structural.get('coverage', 0):.1%}, "
        f"coverage_hq={structural.get('coverage_high_quality', 0):.1%}, "
        f"coverage_candidate={structural.get('coverage_candidate_set', 0):.1%}",
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

    # ── Graph connectivity metrics (same family as build quality gate) ──
    graph_connectivity = _compute_graph_connectivity_metrics(
        concepts,
        edges,
        candidate_concept_ids,
    )
    risk_metrics = _compute_fragmentation_and_risk_metrics(concepts, edges, concept_doc_sets)
    manual_review = _compute_manual_review_metrics(edges)
    cross_lang_consistency = _compute_cross_lang_consistency(concepts, edges)
    active_learning = _compute_active_learning_metrics(session, taxonomy_version_id, collection_id)
    structural["largest_component_ratio"] = (
        graph_connectivity.get("all_concepts", {}).get("largest_component_ratio", 0.0)
    )
    structural["hubness"] = graph_connectivity.get("all_concepts", {}).get("hubness", 0.0)
    structural["lexical_noise_rate"] = (
        graph_connectivity.get("all_concepts", {}).get("lexical_noise_rate", 0.0)
    )
    structural["component_count"] = risk_metrics.get("component_count", 0)
    structural["fragmentation_index"] = risk_metrics.get("fragmentation_index", 0.0)
    structural["small_components_count"] = risk_metrics.get("small_components_count", 0)
    for lang, values in (structural.get("by_language") or {}).items():
        coverage_lang = float(values.get("coverage", 0.0) or 0.0)
        values["min_coverage_target"] = round(float(config.per_lang_min_coverage), 4)
        values["meets_min_coverage"] = coverage_lang >= float(config.per_lang_min_coverage)
        structural["by_language"][lang] = values

    add_job_event(
        session,
        job_id,
        "INFO",
        f"Fragmentation/risk: components={risk_metrics.get('component_count', 0)}, "
        f"fragmentation_index={risk_metrics.get('fragmentation_index', 0.0):.3f}, "
        f"low_score_edges={risk_metrics.get('low_score_edge_count', 0)}, "
        f"orientation_risk={risk_metrics.get('orientation_risk_count', 0)}, "
        f"manual_disagreement={manual_review.get('manual_disagreement_rate', 0.0):.3f}, "
        f"cross_lang_consistency={cross_lang_consistency.get('cross_lang_consistency', 1.0):.3f}",
    )

    # ── Compose quality report ───────────────────────────
    quality_score_10 = _compute_quality_score_10(
        structural=structural,
        graph_connectivity=graph_connectivity,
        risk=risk_metrics,
        manual_review=manual_review,
    )
    quality_metrics = {
        "schema_version": 2,
        "structural": structural,
        "graph_connectivity": graph_connectivity,
        "edge_confidence": edge_stats,
        "risk": risk_metrics,
        "manual_review": manual_review,
        "cross_lang_consistency": cross_lang_consistency,
        "active_learning": active_learning,
        "quality_score_10": quality_score_10,
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
        f"coverage_hq={structural.get('coverage_high_quality', 0):.1%}, "
        f"coverage_candidate={structural.get('coverage_candidate_set', 0):.1%}, "
        f"edges={structural.get('total_edges', 0)}, "
        f"avg_confidence={edge_stats.get('avg_score', 0):.3f}, "
        f"quality_score_10={quality_score_10:.2f}",
    )

    log.info(
        "Evaluation complete for taxonomy %s: %d concepts, %d edges, coverage=%.1f%%",
        taxonomy_version_id,
        structural.get("total_concepts", 0),
        structural.get("total_edges", 0),
        structural.get("coverage", 0) * 100,
    )
