"""
Taxonomy Builder handler.
Orchestrates Hearst + embedding methods, post-processing, quality gates, and DB writes.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter
from collections import defaultdict

from sqlalchemy.orm import Session

from app.config import config
from app.db import Concept, ConceptOccurrence, Document, DocumentChunk, TaxonomyEdge
from app.job_helper import (
    add_job_event,
    is_job_cancelled,
    update_job_status,
    update_taxonomy_status,
)
from app.logger import get_logger
from app.pipeline.taxonomy_embedding import build_embedding_hierarchy
from app.pipeline.taxonomy_linking import bridge_components, safe_link_orphans
from app.pipeline.taxonomy_quality import (
    compute_graph_quality,
    evaluate_quality_gate,
    limit_depth,
    remove_cycles,
)
from app.pipeline.taxonomy_text import extract_hearst_pairs, is_low_quality_label

log = get_logger(__name__)
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
BAD_PARENT_SINGLE_TOKENS = {
    "also", "which", "usually", "many", "significant", "typically", "over",
    "major", "mostly", "often", "much", "several", "various",
    "about", "around", "including", "include", "among", "during",
    "том", "числе", "около", "примерно", "также",
    "кез", "кезінде", "үшін", "арқылы", "мен", "және", "немесе",
}
BAD_PARENT_PHRASES = {
    "том числе",
    "в том числе",
    "составляет около",
    "около",
    "кез келген",
    "соның ішінде",
}
VERBISH_SUFFIXES = (
    "ing", "ed", "ize", "ise", "ать", "ять", "ить", "еть", "ться",
    "ған", "ген", "атын", "етін", "ып", "іп",
)


def _dedupe_pairs(pairs: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for p in pairs:
        key = (p["hypernym"], p["hyponym"])
        if key not in merged:
            merged[key] = p
            continue
        cur = merged[key]
        cur["score"] = max(float(cur.get("score", 0.0)), float(p.get("score", 0.0)))
        ev1 = cur.get("evidence", [])
        ev2 = p.get("evidence", [])
        if isinstance(ev1, dict):
            ev1 = [ev1]
        if isinstance(ev2, dict):
            ev2 = [ev2]
        cur["evidence"] = ev1 + ev2
        merged[key] = cur
    return list(merged.values())


def _edge_rank_score(
    edge: dict,
    concept_doc_freq: dict[str, int],
) -> float:
    parent = edge["hypernym"]
    child = edge["hyponym"]
    base = float(edge.get("score", 0.0))
    pt = TOKEN_RE.findall(parent.lower())
    ct = TOKEN_RE.findall(child.lower())
    score = base
    if _is_valid_parent_label(parent, concept_doc_freq):
        score += 0.08
    # Prefer parent not longer than child in taxonomy orientation.
    if len(pt) <= len(ct):
        score += 0.05
    else:
        score -= 0.03
    score += 0.02 * min(5, concept_doc_freq.get(parent, 0))
    score -= 0.01 * max(0, concept_doc_freq.get(child, 0) - concept_doc_freq.get(parent, 0))
    return score


def _collapse_bidirectional_pairs(
    pairs: list[dict],
    concept_doc_freq: dict[str, int],
) -> list[dict]:
    by_key: dict[tuple[str, str], dict] = {(p["hypernym"], p["hyponym"]): p for p in pairs}
    visited: set[tuple[str, str]] = set()
    out: list[dict] = []
    for key, edge in by_key.items():
        if key in visited:
            continue
        a, b = key
        rev_key = (b, a)
        if rev_key not in by_key:
            out.append(edge)
            visited.add(key)
            continue
        rev = by_key[rev_key]
        # keep only stronger orientation
        keep = edge if _edge_rank_score(edge, concept_doc_freq) >= _edge_rank_score(rev, concept_doc_freq) else rev
        out.append(keep)
        visited.add(key)
        visited.add(rev_key)
    return out


def _compute_pair_cooccurrence(
    chunks: list[DocumentChunk],
    concept_labels: list[str],
) -> dict[tuple[str, str], float]:
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    label_presence: dict[str, int] = defaultdict(int)
    labels = [c.strip().lower() for c in concept_labels if len(c.strip()) >= 2]
    if not labels or not chunks:
        return {}
    patterns = {
        lbl: re.compile(rf"(?<!\w){re.escape(lbl)}(?!\w)", re.IGNORECASE)
        for lbl in labels
    }

    for chunk in chunks:
        text = chunk.text
        hits = []
        for lbl, pat in patterns.items():
            if pat.search(text):
                hits.append(lbl)
                label_presence[lbl] += 1
        if len(hits) < 2:
            continue
        uniq = sorted(set(hits))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                pair_counts[(uniq[i], uniq[j])] += 1
                pair_counts[(uniq[j], uniq[i])] += 1

    if not pair_counts:
        return {}

    max_pair = max(pair_counts.values())
    support: dict[tuple[str, str], float] = {}
    for k, v in pair_counts.items():
        a, b = k
        pa = label_presence.get(a, 1)
        pb = label_presence.get(b, 1)
        discount = 1.0 / (1.0 + 0.02 * max(pa + pb - 4, 0))
        support[k] = min(1.0, (v / max_pair) * discount)
    return support


def _compute_concept_doc_freq(
    session: Session,
    concepts: list[Concept],
) -> dict[str, int]:
    if not concepts:
        return {}
    concept_ids = [c.id for c in concepts]
    rows = (
        session.query(ConceptOccurrence.concept_id, DocumentChunk.document_id)
        .join(DocumentChunk, ConceptOccurrence.chunk_id == DocumentChunk.id)
        .filter(ConceptOccurrence.concept_id.in_(concept_ids))
        .all()
    )
    per_concept_docs: dict[str, set[str]] = defaultdict(set)
    for concept_id, document_id in rows:
        per_concept_docs[str(concept_id)].add(str(document_id))
    out: dict[str, int] = {}
    for c in concepts:
        out[c.canonical] = len(per_concept_docs.get(str(c.id), set()))
    return out


def _is_valid_parent_label(label: str, concept_doc_freq: dict[str, int]) -> bool:
    norm = " ".join(TOKEN_RE.findall((label or "").lower())).strip()
    toks = norm.split()
    if not toks:
        return False
    if norm in BAD_PARENT_PHRASES:
        return False
    if any(phrase in norm for phrase in BAD_PARENT_PHRASES if " " in phrase):
        return False
    if len(toks) == 1:
        tok = toks[0]
        if tok in BAD_PARENT_SINGLE_TOKENS:
            return False
        if len(tok) < 4:
            return False
        if concept_doc_freq.get(label, 0) < config.min_parent_doc_freq:
            return False
    if len(toks) == 2 and any(t in BAD_PARENT_SINGLE_TOKENS for t in toks):
        return False
    if len(toks) <= 2 and all(any(tok.endswith(s) for s in VERBISH_SUFFIXES) for tok in toks):
        return False
    return True


def _semantic_from_evidence(edge: dict) -> float:
    ev = edge.get("evidence", [])
    if isinstance(ev, dict):
        ev = [ev]
    best = 0.0
    for item in ev:
        if not isinstance(item, dict):
            continue
        sem = float(item.get("semantic_similarity", 0.0) or 0.0)
        lex = float(item.get("lexical_similarity", 0.0) or 0.0)
        cooc = float(item.get("cooccurrence_support", 0.0) or 0.0)
        best = max(best, (0.65 * sem) + (0.25 * lex) + (0.10 * cooc))
    return best


def _is_edge_plausible(
    edge: dict,
    concept_doc_freq: dict[str, int],
    min_score: float,
) -> bool:
    parent = edge["hypernym"]
    child = edge["hyponym"]
    if not _is_valid_parent_label(parent, concept_doc_freq):
        return False
    if is_low_quality_label(parent) or is_low_quality_label(child):
        return False
    pt = TOKEN_RE.findall(parent.lower())
    ct = TOKEN_RE.findall(child.lower())
    if len(pt) == 1 and len(ct) == 1:
        return False
    if len(pt) > len(ct) + 1:
        return False
    if float(edge.get("score", 0.0)) < min_score:
        return False
    semantic = _semantic_from_evidence(edge)
    if semantic > 0 and semantic < 0.55:
        return False
    return True


def _limit_parent_hubness(
    pairs: list[dict],
    concept_doc_freq: dict[str, int],
    max_children_per_parent: int,
) -> list[dict]:
    if not pairs:
        return []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for p in pairs:
        grouped[p["hypernym"]].append(p)

    capped: list[dict] = []
    hard_cap = max(2, min(max_children_per_parent, 5))
    for parent, edges in grouped.items():
        if len(edges) <= hard_cap:
            capped.extend(edges)
            continue
        edges_sorted = sorted(
            edges,
            key=lambda e: _edge_rank_score(e, concept_doc_freq),
            reverse=True,
        )
        capped.extend(edges_sorted[:hard_cap])
    return capped


def handle_build(session: Session, msg: dict) -> None:
    """Build taxonomy hierarchy."""
    job_id = str(msg.get("jobId") or msg.get("job_id"))
    collection_id = str(msg.get("collectionId") or msg.get("collection_id"))
    taxonomy_version_id = str(msg.get("taxonomyVersionId") or msg.get("taxonomy_version_id"))
    params = msg.get("params", {})

    update_job_status(session, job_id, "RUNNING", progress=0)
    update_taxonomy_status(session, taxonomy_version_id, "RUNNING")
    add_job_event(session, job_id, "INFO", "Taxonomy build started")

    method = params.get("method_taxonomy", "hybrid")
    max_depth = int(params.get("max_depth", config.max_depth))
    sim_threshold = float(params.get("similarity_threshold", config.similarity_threshold))
    parent_pool_size = int(params.get("parent_pool_size", config.parent_pool_size))
    max_children_per_parent = int(
        params.get("max_children_per_parent", config.max_children_per_parent)
    )
    adaptive_percentile = int(params.get("adaptive_percentile", config.adaptive_percentile))
    quality_thresholds = {
        "min_edge_density": float(
            params.get("quality_min_edge_density", config.quality_min_edge_density)
        ),
        "min_largest_component_ratio": float(
            params.get(
                "quality_min_largest_component_ratio",
                config.quality_min_largest_component_ratio,
            )
        ),
        "max_hubness": float(params.get("quality_max_hubness", config.quality_max_hubness)),
        "max_lexical_noise_rate": float(
            params.get("quality_max_lexical_noise_rate", config.quality_max_lexical_noise_rate)
        ),
    }
    enforce_quality_gate = bool(params.get("enforce_quality_gate", False))
    orphan_linking_enabled = bool(
        params.get("orphan_linking_enabled", config.orphan_linking_enabled)
    )
    orphan_link_threshold = float(
        params.get("orphan_link_threshold", config.orphan_link_threshold)
    )
    orphan_link_max_links = int(
        params.get("orphan_link_max_links", config.orphan_link_max_links)
    )
    component_bridging_enabled = bool(
        params.get("component_bridging_enabled", config.component_bridging_enabled)
    )
    component_bridge_threshold = float(
        params.get("component_bridge_threshold", config.component_bridge_threshold)
    )
    component_bridge_max_links = int(
        params.get("component_bridge_max_links", config.component_bridge_max_links)
    )
    min_parent_doc_freq = int(
        params.get("min_parent_doc_freq", config.min_parent_doc_freq)
    )

    concepts = (
        session.query(Concept)
        .filter(Concept.collection_id == collection_id)
        .all()
    )
    if not concepts:
        add_job_event(session, job_id, "WARN", "No concepts found — skipping build")
        update_taxonomy_status(session, taxonomy_version_id, "READY")
        update_job_status(session, job_id, "RUNNING", progress=100)
        return

    concept_set = {c.canonical for c in concepts}
    concept_map = {c.canonical: c for c in concepts}
    concept_doc_freq = _compute_concept_doc_freq(session, concepts)
    concept_scores = {c.canonical: float(c.score or 0.0) for c in concepts}

    docs = (
        session.query(Document)
        .filter(Document.collection_id == collection_id, Document.status == "PARSED")
        .all()
    )
    doc_ids = [str(d.id) for d in docs]
    chunks = (
        session.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(doc_ids))
        .all()
    )

    lang_groups: dict[str, list[DocumentChunk]] = defaultdict(list)
    for chunk in chunks:
        lang = (chunk.lang or config.default_language or "en").lower()[:2]
        lang_groups[lang].append(chunk)
    lang_counts = Counter({k: len(v) for k, v in lang_groups.items()})
    dominant_lang = lang_counts.most_common(1)[0][0] if lang_counts else "en"
    cooc_support = _compute_pair_cooccurrence(chunks, list(concept_set))

    all_pairs: list[dict] = []

    if method in ("hearst", "hybrid"):
        hearst_pairs: list[dict] = []
        for lang, group_chunks in lang_groups.items():
            hearst_pairs.extend(extract_hearst_pairs(group_chunks, concept_set, lang))
        all_pairs.extend(hearst_pairs)
        add_job_event(
            session, job_id, "INFO",
            f"Hearst patterns found {len(hearst_pairs)} relations across langs={dict(lang_counts)}",
        )
        update_job_status(session, job_id, "RUNNING", progress=30)

    if is_job_cancelled(session, job_id):
        return

    if method in ("embedding", "hybrid"):
        emb_pairs = build_embedding_hierarchy(
            concepts,
            sim_threshold,
            parent_pool_size=parent_pool_size,
            max_children_per_parent=max_children_per_parent,
            adaptive_percentile=adaptive_percentile,
            concept_doc_freq=concept_doc_freq,
            min_parent_doc_freq=min_parent_doc_freq,
        )
        all_pairs.extend(emb_pairs)
        add_job_event(
            session, job_id, "INFO",
            f"Embedding clustering found {len(emb_pairs)} relations",
        )
        update_job_status(session, job_id, "RUNNING", progress=60)

    if not all_pairs:
        add_job_event(session, job_id, "WARN", "No taxonomy relations found")
        update_taxonomy_status(session, taxonomy_version_id, "READY")
        update_job_status(session, job_id, "RUNNING", progress=100)
        return

    seen_pairs: set[tuple[str, str]] = set()
    unique_pairs: list[dict] = []
    for pair in all_pairs:
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

    unique_pairs = _collapse_bidirectional_pairs(unique_pairs, concept_doc_freq)
    unique_pairs = remove_cycles(unique_pairs)
    unique_pairs = limit_depth(unique_pairs, max_depth)
    min_edge_accept_score = float(params.get("min_edge_accept_score", config.min_edge_accept_score))
    unique_pairs = [
        e for e in unique_pairs if _is_edge_plausible(e, concept_doc_freq, min_edge_accept_score)
    ]
    for e in unique_pairs:
        base = float(e.get("score", 0.0))
        cooc = float(cooc_support.get((e["hypernym"], e["hyponym"]), 0.0))
        composite = (0.75 * base) + (0.25 * cooc)
        e["score"] = round(composite, 4)
        ev = e.get("evidence", {})
        if isinstance(ev, dict):
            ev["cooccurrence_support"] = round(cooc, 4)
            ev["composite_score"] = round(composite, 4)
            e["evidence"] = ev
    if orphan_linking_enabled:
        concept_labels = [c.canonical for c in concepts]
        orphan_links = safe_link_orphans(
            unique_pairs,
            concept_labels,
            threshold=orphan_link_threshold,
            max_links=orphan_link_max_links,
            concept_doc_freq=concept_doc_freq,
            concept_scores=concept_scores,
            min_orphan_doc_freq=2,
            min_orphan_score=0.25,
        )
        if orphan_links:
            unique_pairs.extend(
                [
                    e for e in orphan_links
                    if _is_edge_plausible(e, concept_doc_freq, min_edge_accept_score)
                ]
            )
            add_job_event(
                session,
                job_id,
                "INFO",
                f"Orphan safe-linking added {len(orphan_links)} edges "
                f"(threshold={orphan_link_threshold:.2f})",
            )
        # Second adaptive pass if graph is still sparse.
        interim_quality = compute_graph_quality(unique_pairs, len(concepts))
        if interim_quality["largest_component_ratio"] < 0.20:
            second_threshold = max(0.50, orphan_link_threshold - 0.06)
            extra_links = safe_link_orphans(
                unique_pairs,
                concept_labels,
                threshold=second_threshold,
                max_links=max(5, orphan_link_max_links // 2),
                concept_doc_freq=concept_doc_freq,
                concept_scores=concept_scores,
                min_orphan_doc_freq=2,
                min_orphan_score=0.25,
            )
            if extra_links:
                unique_pairs.extend(
                    [
                        e for e in extra_links
                        if _is_edge_plausible(e, concept_doc_freq, min_edge_accept_score)
                    ]
                )
                add_job_event(
                    session,
                    job_id,
                    "INFO",
                    f"Orphan safe-linking second pass added {len(extra_links)} edges "
                    f"(threshold={second_threshold:.2f})",
                )
    if component_bridging_enabled:
        interim_quality = compute_graph_quality(unique_pairs, len(concepts))
        if interim_quality["largest_component_ratio"] >= 0.55:
            component_bridging_enabled = False
            add_job_event(
                session,
                job_id,
                "INFO",
                "Component bridging skipped (graph already sufficiently connected)",
            )
    if component_bridging_enabled:
        effective_bridge_threshold = max(component_bridge_threshold, 0.62)
        effective_bridge_max_links = min(component_bridge_max_links, max(6, len(concepts) // 10))
        bridges = bridge_components(
            unique_pairs,
            threshold=effective_bridge_threshold,
            max_links=effective_bridge_max_links,
            concept_labels=[c.canonical for c in concepts],
        )
        if bridges:
            unique_pairs.extend(
                [e for e in bridges if _is_edge_plausible(e, concept_doc_freq, min_edge_accept_score)]
            )
            add_job_event(
                session,
                job_id,
                "INFO",
                f"Component bridging added {len(bridges)} edges "
                f"(threshold={effective_bridge_threshold:.2f})",
            )

    unique_pairs = _dedupe_pairs(unique_pairs)
    unique_pairs = _collapse_bidirectional_pairs(unique_pairs, concept_doc_freq)
    unique_pairs = _limit_parent_hubness(
        unique_pairs,
        concept_doc_freq,
        max_children_per_parent=max_children_per_parent,
    )

    quality_candidate_count = sum(
        1
        for c in concepts
        if not is_low_quality_label(c.canonical) and concept_doc_freq.get(c.canonical, 0) >= 2
    )
    quality_total = max(1, quality_candidate_count)
    quality_report = compute_graph_quality(unique_pairs, quality_total)
    violations = evaluate_quality_gate(quality_report, quality_thresholds)
    add_job_event(
        session,
        job_id,
        "INFO",
        "Quality gate metrics: "
        f"edge_density={quality_report['edge_density']:.3f}, "
        f"largest_component_ratio={quality_report['largest_component_ratio']:.3f}, "
        f"hubness={quality_report['hubness']:.3f}, "
        f"lexical_noise_rate={quality_report['lexical_noise_rate']:.3f}",
    )
    if violations:
        add_job_event(session, job_id, "WARN", "Quality gate violations: " + "; ".join(violations))
        if enforce_quality_gate:
            update_taxonomy_status(session, taxonomy_version_id, "FAILED")
            update_job_status(
                session,
                job_id,
                "FAILED",
                progress=100,
                error_message="Quality gate failed: " + "; ".join(violations),
            )
            return

    add_job_event(session, job_id, "INFO", f"After post-processing: {len(unique_pairs)} edges")
    update_job_status(session, job_id, "RUNNING", progress=80)

    session.query(TaxonomyEdge).filter(
        TaxonomyEdge.taxonomy_version_id == taxonomy_version_id
    ).delete()
    session.commit()

    stored = 0
    for pair in unique_pairs:
        parent = concept_map.get(pair["hypernym"])
        child = concept_map.get(pair["hyponym"])
        if not parent or not child:
            continue
        edge = TaxonomyEdge(
            id=uuid.uuid4(),
            taxonomy_version_id=taxonomy_version_id,
            parent_concept_id=parent.id,
            child_concept_id=child.id,
            relation="is_a",
            score=pair["score"],
            evidence=[pair["evidence"]] if isinstance(pair["evidence"], dict) else pair["evidence"],
        )
        session.add(edge)
        stored += 1
        if stored % 100 == 0:
            session.commit()
    session.commit()

    update_taxonomy_status(session, taxonomy_version_id, "READY")
    add_job_event(session, job_id, "INFO", f"Taxonomy build complete: {stored} edges, method={method}")
    update_job_status(session, job_id, "RUNNING", progress=100)
    log.info(
        "Taxonomy build complete: collection=%s version=%s edges=%d",
        collection_id,
        taxonomy_version_id,
        stored,
    )
