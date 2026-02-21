"""
Taxonomy Builder worker
───────────────────────
Two methods for building is-a hierarchies:

  Method A: Hearst Patterns (rule-based)
  Method B: Embedding clustering + parent selection

Plus post-processing: cycle removal, depth limiting, merging.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.config import config
from app.db import (
    Concept, DocumentChunk, TaxonomyEdge, TaxonomyVersion, Document,
)
from app.job_helper import (
    update_job_status, add_job_event, update_taxonomy_status, is_job_cancelled,
)
from app.logger import get_logger

log = get_logger(__name__)


# ══════════════════════════════════════════════════════════
# Method A: Hearst Patterns
# ══════════════════════════════════════════════════════════

# English patterns
HEARST_PATTERNS_EN = [
    # "X such as Y, Z, and W"
    (r"([\w\s]+?)\s+such\s+as\s+([\w\s,]+?)(?:\.|,\s*and\s|\s+and\s)", "hypernym", "hyponyms"),
    # "Y and other X"
    (r"([\w\s,]+?)\s+and\s+other\s+([\w\s]+?)(?:\.|,|;)", "hyponyms", "hypernym"),
    # "X, including Y"
    (r"([\w\s]+?)\s*,?\s*including\s+([\w\s,]+?)(?:\.|,\s*and\s|\s+and\s)", "hypernym", "hyponyms"),
    # "X, especially Y"
    (r"([\w\s]+?)\s*,?\s*especially\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    # "Y is a (kind|type|form) of X"
    (r"([\w\s]+?)\s+is\s+a\s+(?:kind|type|form|sort)\s+of\s+([\w\s]+?)(?:\.|,)", "hyponym", "hypernym"),
]

# Russian patterns
HEARST_PATTERNS_RU = [
    # "X, такие как Y, Z"
    (r"([\w\s]+?)\s*,?\s*такие?\s+как\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    # "Y и другие X"
    (r"([\w\s,]+?)\s+и\s+други[еих]\s+([\w\s]+?)(?:\.|,)", "hyponyms", "hypernym"),
    # "X, в частности Y"
    (r"([\w\s]+?)\s*,?\s*в\s+частности\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    # "X, например Y"
    (r"([\w\s]+?)\s*,?\s*например\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    # "Y является (видом|разновидностью) X"
    (r"([\w\s]+?)\s+является\s+(?:видом|разновидностью|типом)\s+([\w\s]+?)(?:\.|,)", "hyponym", "hypernym"),
]


def _split_enumeration(text: str) -> list[str]:
    """Split 'A, B, and C' into ['A', 'B', 'C']."""
    parts = re.split(r"\s*,\s*|\s+and\s+|\s+и\s+", text)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 1]


def extract_hearst_pairs(
    chunks: list[DocumentChunk],
    concept_set: set[str],
    lang: str = "en",
) -> list[dict]:
    """
    Extract (hypernym, hyponym) pairs using Hearst patterns.
    Returns list of {hypernym, hyponym, score, evidence}.
    """
    patterns = HEARST_PATTERNS_EN if lang.startswith("en") else HEARST_PATTERNS_RU
    pairs: list[dict] = []

    for chunk in chunks:
        text = chunk.text
        for pattern_str, group1_role, group2_role in patterns:
            for match in re.finditer(pattern_str, text, re.IGNORECASE):
                g1 = match.group(1).strip().lower()
                g2 = match.group(2).strip().lower()

                if group1_role == "hypernym":
                    hypernym_raw = g1
                    hyponym_raws = _split_enumeration(g2) if "hyponyms" in group2_role else [g2]
                elif group1_role == "hyponym":
                    hypernym_raw = g2
                    hyponym_raws = [g1]
                else:
                    hypernym_raw = g2
                    hyponym_raws = _split_enumeration(g1)

                # Check if terms are in concept set
                hypernym_clean = hypernym_raw.strip()
                if hypernym_clean not in concept_set:
                    # Try partial match
                    hypernym_match = _find_closest_concept(hypernym_clean, concept_set)
                    if hypernym_match:
                        hypernym_clean = hypernym_match
                    else:
                        continue

                for hypo_raw in hyponym_raws:
                    hypo_clean = hypo_raw.strip()
                    if hypo_clean not in concept_set:
                        hypo_match = _find_closest_concept(hypo_clean, concept_set)
                        if hypo_match:
                            hypo_clean = hypo_match
                        else:
                            continue

                    if hypernym_clean == hypo_clean:
                        continue

                    # Create snippet evidence
                    snippet_start = max(0, match.start() - 30)
                    snippet_end = min(len(text), match.end() + 30)

                    pairs.append({
                        "hypernym": hypernym_clean,
                        "hyponym": hypo_clean,
                        "score": 0.7,
                        "evidence": {
                            "chunk_id": str(chunk.id),
                            "snippet": text[snippet_start:snippet_end],
                            "pattern": pattern_str[:50],
                            "method": "hearst",
                        },
                    })

    return pairs


def _find_closest_concept(text: str, concept_set: set[str]) -> str | None:
    """Find the closest matching concept (simple substring check)."""
    text = text.lower().strip()
    for concept in concept_set:
        if concept in text or text in concept:
            return concept
    return None


# ══════════════════════════════════════════════════════════
# Method B: Embedding + Clustering
# ══════════════════════════════════════════════════════════

def build_embedding_hierarchy(
    concepts: list[Concept],
    similarity_threshold: float | None = None,
) -> list[dict]:
    """
    Build hierarchy using sentence embeddings:
    1. Embed all terms
    2. Cluster with HDBSCAN
    3. Within each cluster, select parent (shortest/most frequent)
    4. Assign children by cosine similarity
    """
    if similarity_threshold is None:
        similarity_threshold = config.similarity_threshold

    if len(concepts) < 3:
        return []

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        log.warning("sentence-transformers not available, skipping embedding method")
        return []

    add_log = log.info

    # Load model (multilingual)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    terms = [c.canonical for c in concepts]
    embeddings = model.encode(terms, show_progress_bar=False, normalize_embeddings=True)

    # Cluster
    try:
        import hdbscan
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=max(2, len(concepts) // 20),
            min_samples=1,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(embeddings)
    except Exception:
        # Fallback to KMeans
        from sklearn.cluster import KMeans
        n_clusters = max(2, min(len(concepts) // 5, 20))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

    log.info("Clustered %d concepts into %d clusters", len(concepts), len(set(labels)))

    # Group by cluster
    clusters: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        if label >= 0:
            clusters[label].append(idx)

    pairs: list[dict] = []

    for cluster_id, indices in clusters.items():
        if len(indices) < 2:
            continue

        # Select parent: highest score + shorter canonical → more general
        cluster_concepts = [(i, concepts[i]) for i in indices]
        cluster_concepts.sort(key=lambda x: (
            -x[1].score,
            len(x[1].canonical),  # shorter is more general
        ))

        parent_idx, parent_concept = cluster_concepts[0]

        # Assign children
        for child_idx, child_concept in cluster_concepts[1:]:
            if parent_concept.canonical == child_concept.canonical:
                continue

            # Cosine similarity
            sim = float(np.dot(embeddings[parent_idx], embeddings[child_idx]))
            if sim < similarity_threshold:
                continue

            pairs.append({
                "hypernym": parent_concept.canonical,
                "hyponym": child_concept.canonical,
                "score": round(sim, 4),
                "evidence": {
                    "method": "embedding_clustering",
                    "cluster_id": int(cluster_id),
                    "cosine_similarity": round(sim, 4),
                },
            })

    return pairs


# ══════════════════════════════════════════════════════════
# Post-processing
# ══════════════════════════════════════════════════════════

def remove_cycles(edges: list[dict]) -> list[dict]:
    """Remove cycles by breaking weakest edges using DFS."""
    # Build adjacency
    graph: dict[str, list[tuple[str, float, int]]] = defaultdict(list)
    for i, e in enumerate(edges):
        graph[e["hypernym"]].append((e["hyponym"], e["score"], i))

    visited: set[str] = set()
    in_stack: set[str] = set()
    remove_indices: set[int] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        in_stack.add(node)
        for child, score, idx in graph.get(node, []):
            if child in in_stack:
                # Cycle found — remove this edge (weakest heuristic)
                remove_indices.add(idx)
            elif child not in visited:
                dfs(child)
        in_stack.discard(node)

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node)

    return [e for i, e in enumerate(edges) if i not in remove_indices]


def limit_depth(edges: list[dict], max_depth: int) -> list[dict]:
    """Limit tree depth by removing edges beyond max_depth from roots."""
    # Find roots (parents that are never children)
    parents = {e["hypernym"] for e in edges}
    children_set = {e["hyponym"] for e in edges}
    roots = parents - children_set

    if not roots:
        return edges

    # BFS to compute depth
    child_to_parents: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        child_to_parents[e["hyponym"]].append(e["hypernym"])

    depths: dict[str, int] = {}
    queue = list(roots)
    for r in roots:
        depths[r] = 0

    while queue:
        node = queue.pop(0)
        parent_to_children = defaultdict(list)
        for e in edges:
            parent_to_children[e["hypernym"]].append(e["hyponym"])

        for child in parent_to_children.get(node, []):
            if child not in depths:
                depths[child] = depths[node] + 1
                queue.append(child)

    return [
        e for e in edges
        if depths.get(e["hyponym"], 0) <= max_depth
    ]


# ══════════════════════════════════════════════════════════
# Main Handler
# ══════════════════════════════════════════════════════════

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

    # Load concepts
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

    # Load chunks for Hearst patterns
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

    # Detect dominant language
    from collections import Counter
    lang_counts = Counter(c.lang for c in chunks if c.lang)
    dominant_lang = lang_counts.most_common(1)[0][0] if lang_counts else "en"

    all_pairs: list[dict] = []

    # ── Method A: Hearst ─────────────────────────────────
    if method in ("hearst", "hybrid"):
        hearst_pairs = extract_hearst_pairs(chunks, concept_set, dominant_lang)
        all_pairs.extend(hearst_pairs)
        add_job_event(
            session, job_id, "INFO",
            f"Hearst patterns found {len(hearst_pairs)} relations",
        )
        update_job_status(session, job_id, "RUNNING", progress=30)

    if is_job_cancelled(session, job_id):
        return

    # ── Method B: Embeddings ─────────────────────────────
    if method in ("embedding", "hybrid"):
        emb_pairs = build_embedding_hierarchy(concepts, sim_threshold)
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

    # ── Deduplicate pairs ────────────────────────────────
    seen_pairs: set[tuple[str, str]] = set()
    unique_pairs: list[dict] = []
    for pair in all_pairs:
        key = (pair["hypernym"], pair["hyponym"])
        if key not in seen_pairs:
            seen_pairs.add(key)
            unique_pairs.append(pair)
        else:
            # Merge: keep highest score
            for up in unique_pairs:
                if (up["hypernym"], up["hyponym"]) == key:
                    up["score"] = max(up["score"], pair["score"])
                    break

    # ── Post-processing ──────────────────────────────────
    unique_pairs = remove_cycles(unique_pairs)
    unique_pairs = limit_depth(unique_pairs, max_depth)

    add_job_event(
        session, job_id, "INFO",
        f"After post-processing: {len(unique_pairs)} edges",
    )
    update_job_status(session, job_id, "RUNNING", progress=80)

    # ── Delete existing edges for this version (idempotency) ──
    session.query(TaxonomyEdge).filter(
        TaxonomyEdge.taxonomy_version_id == taxonomy_version_id
    ).delete()
    session.commit()

    # ── Store edges ──────────────────────────────────────
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

    # ── Finalize ─────────────────────────────────────────
    update_taxonomy_status(session, taxonomy_version_id, "READY")
    add_job_event(
        session, job_id, "INFO",
        f"Taxonomy build complete: {stored} edges, method={method}",
    )
    update_job_status(session, job_id, "RUNNING", progress=100)
    log.info(
        "Taxonomy build complete: collection=%s version=%s edges=%d",
        collection_id, taxonomy_version_id, stored,
    )
