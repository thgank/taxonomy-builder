from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy.orm import Session

from app.config import config
from app.db import Concept, ConceptOccurrence, Document, DocumentChunk
from app.pipeline.term_extraction_cleaning import compile_term_pattern
from app.pipeline.taxonomy_build.edge_filters import parent_validity_score
from app.pipeline.taxonomy_build.graph_metrics import edge_key

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def edge_rank_score(edge: dict, concept_doc_freq: dict[str, int]) -> float:
    parent = edge["hypernym"]
    child = edge["hyponym"]
    base = float(edge.get("score", 0.0))
    pt = TOKEN_RE.findall(parent.lower())
    ct = TOKEN_RE.findall(child.lower())
    score = base
    score += 0.10 * parent_validity_score(parent, concept_doc_freq)
    if len(pt) <= len(ct):
        score += 0.05
    else:
        score -= 0.03
    score += 0.02 * min(5, concept_doc_freq.get(parent, 0))
    score -= 0.01 * max(0, concept_doc_freq.get(child, 0) - concept_doc_freq.get(parent, 0))
    return score


def method_weight(method: str) -> float:
    m = (method or "").lower()
    if m == "hearst":
        return 0.72
    if m == "hearst_trigger_fallback":
        return 0.62
    if m == "embedding_clustering":
        return 0.64
    if m == "embedding_clustering_secondary_parent":
        return 0.60
    if m == "embedding_clustering_relaxed":
        return 0.56
    if m == "component_bridge":
        return 0.58
    if m == "orphan_safe_link":
        return 0.55
    return 0.60


def collapse_bidirectional_pairs(pairs: list[dict], concept_doc_freq: dict[str, int]) -> list[dict]:
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
        keep = edge if edge_rank_score(edge, concept_doc_freq) >= edge_rank_score(rev, concept_doc_freq) else rev
        out.append(keep)
        visited.add(key)
        visited.add(rev_key)
    return out


def compute_pair_cooccurrence(chunks: list[DocumentChunk], concept_labels: list[str]) -> dict[tuple[str, str], float]:
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    label_presence: dict[str, int] = defaultdict(int)
    labels = [c.strip().lower() for c in concept_labels if len(c.strip()) >= 2]
    if not labels or not chunks:
        return {}
    patterns = {lbl: re.compile(rf"(?<!\w){re.escape(lbl)}(?!\w)", re.IGNORECASE) for lbl in labels}
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


def compute_concept_doc_freq(session: Session, concepts: list[Concept]) -> dict[str, int]:
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

    # Concept occurrences are capped per term; this can underestimate doc-freq
    # and cause valid parents to be rejected. Recompute exact df for low-df terms.
    collection_id = concepts[0].collection_id
    refine_labels = [
        c.canonical
        for c in concepts
        if out.get(c.canonical, 0) < int(max(1, config.min_parent_doc_freq))
    ]
    if not refine_labels:
        return out

    doc_ids = [
        d[0]
        for d in (
            session.query(Document.id)
            .filter(
                Document.collection_id == collection_id,
                Document.status == "PARSED",
            )
            .all()
        )
    ]
    if not doc_ids:
        return out

    patterns = {label: compile_term_pattern(label) for label in refine_labels}
    refined_docs: dict[str, set[str]] = {label: set() for label in refine_labels}
    rows = (
        session.query(DocumentChunk.document_id, DocumentChunk.text)
        .filter(DocumentChunk.document_id.in_(doc_ids))
        .yield_per(500)
    )
    for doc_id, chunk_text in rows:
        text = chunk_text or ""
        if not text:
            continue
        doc_key = str(doc_id)
        for label, pattern in patterns.items():
            if pattern.search(text):
                refined_docs[label].add(doc_key)
    for label, docs in refined_docs.items():
        out[label] = max(out.get(label, 0), len(docs))
    return out


def connectivity_critical_edge_keys(
    pairs: list[dict],
    concept_labels: list[str],
    concept_doc_freq: dict[str, int],
) -> set[tuple[str, str]]:
    nodes = list(dict.fromkeys(concept_labels))
    if not nodes or not pairs:
        return set()
    parent: dict[str, str] = {n: n for n in nodes}
    rank: dict[str, int] = {n: 0 for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> bool:
        ra = find(a)
        rb = find(b)
        if ra == rb:
            return False
        if rank[ra] < rank[rb]:
            parent[ra] = rb
        elif rank[ra] > rank[rb]:
            parent[rb] = ra
        else:
            parent[rb] = ra
            rank[ra] += 1
        return True

    ranked = sorted(pairs, key=lambda e: edge_rank_score(e, concept_doc_freq), reverse=True)
    critical: set[tuple[str, str]] = set()
    for e in ranked:
        p = e["hypernym"]
        c = e["hyponym"]
        if p not in parent:
            parent[p] = p
            rank[p] = 0
        if c not in parent:
            parent[c] = c
            rank[c] = 0
        if union(p, c):
            critical.add(edge_key(e))
    return critical


def cap_protected_edge_keys_by_parent(
    pairs: list[dict],
    protected_edge_keys: set[tuple[str, str]],
    concept_doc_freq: dict[str, int],
    max_per_parent: int,
) -> set[tuple[str, str]]:
    if not protected_edge_keys:
        return set()
    if max_per_parent <= 0:
        return set()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for edge in pairs:
        key = edge_key(edge)
        if key in protected_edge_keys:
            grouped[edge["hypernym"]].append(edge)

    capped: set[tuple[str, str]] = set()
    for parent_edges in grouped.values():
        ranked = sorted(
            parent_edges,
            key=lambda e: edge_rank_score(e, concept_doc_freq),
            reverse=True,
        )
        for edge in ranked[:max_per_parent]:
            capped.add(edge_key(edge))
    return capped


def limit_parent_hubness(
    pairs: list[dict],
    concept_doc_freq: dict[str, int],
    max_children_per_parent: int,
    protected_edge_keys: set[tuple[str, str]] | None = None,
) -> list[dict]:
    if not pairs:
        return []
    if protected_edge_keys is None:
        protected_edge_keys = set()
    grouped: dict[str, list[dict]] = defaultdict(list)
    for p in pairs:
        grouped[p["hypernym"]].append(p)

    capped: list[dict] = []
    hard_cap = max(2, min(max_children_per_parent, 5))
    for parent, edges in grouped.items():
        if len(edges) <= hard_cap:
            capped.extend(edges)
            continue
        edges_sorted = sorted(edges, key=lambda e: edge_rank_score(e, concept_doc_freq), reverse=True)
        protected = [e for e in edges_sorted if edge_key(e) in protected_edge_keys]
        protected_keys = {edge_key(e) for e in protected}
        regular = [e for e in edges_sorted if edge_key(e) not in protected_keys]
        keep_regular = regular[: max(0, hard_cap - len(protected))]
        capped.extend(protected + keep_regular)
    return capped
