from __future__ import annotations

from collections import defaultdict

import numpy as np

from app.config import config
from app.db import Concept
from app.logger import get_logger
from app.pipeline.taxonomy_text import (
    GENERIC_PARENT_TERMS,
    GENERIC_TERMS,
    is_low_quality_label,
    tokenize,
)

log = get_logger(__name__)


def build_embedding_hierarchy(
    concepts: list[Concept],
    similarity_threshold: float | None = None,
    parent_pool_size: int | None = None,
    max_children_per_parent: int | None = None,
    adaptive_percentile: int | None = None,
    concept_doc_freq: dict[str, int] | None = None,
    min_parent_doc_freq: int | None = None,
) -> list[dict]:
    if similarity_threshold is None:
        similarity_threshold = config.similarity_threshold
    if parent_pool_size is None:
        parent_pool_size = config.parent_pool_size
    if max_children_per_parent is None:
        max_children_per_parent = config.max_children_per_parent
    if adaptive_percentile is None:
        adaptive_percentile = config.adaptive_percentile
    if min_parent_doc_freq is None:
        min_parent_doc_freq = config.min_parent_doc_freq
    if concept_doc_freq is None:
        concept_doc_freq = {}

    if len(concepts) < 3:
        return []

    def is_weak_single_child(label: str) -> bool:
        toks = tokenize(label)
        if len(toks) != 1:
            return False
        return concept_doc_freq.get(label, 0) < 3

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        log.warning("sentence-transformers not available, skipping embedding method")
        return []

    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    terms = [c.canonical for c in concepts]
    embeddings = model.encode(terms, show_progress_bar=False, normalize_embeddings=True)

    used_hdbscan = False
    try:
        import hdbscan
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=max(2, len(concepts) // 20),
            min_samples=1,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(embeddings)
        used_hdbscan = True
    except Exception:
        labels = None

    if labels is None or (used_hdbscan and all(int(x) < 0 for x in labels)):
        from sklearn.cluster import KMeans

        n_clusters = max(2, min(len(concepts) // 5, 20))
        labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(embeddings)

    log.info("Clustered %d concepts into %d clusters", len(concepts), len(set(labels)))
    clusters: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        if label >= 0:
            clusters[label].append(idx)

    pairs: list[dict] = []
    edge_keys: set[tuple[str, str]] = set()
    for cluster_id, indices in clusters.items():
        if len(indices) < 2:
            continue
        cluster_vecs = np.array([embeddings[i] for i in indices])
        centroid = cluster_vecs.mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm

        token_cluster_freq: dict[str, int] = defaultdict(int)
        for i in indices:
            for t in set(tokenize(concepts[i].canonical)):
                token_cluster_freq[t] += 1
        cluster_size = max(1, len(indices))

        def parent_penalty(label: str) -> float:
            toks = tokenize(label.lower())
            if not toks:
                return 1.0
            p = 0.0
            if len(toks) == 1:
                p += 0.28
            if any(t in GENERIC_PARENT_TERMS for t in toks):
                p += 0.22
            if any(t in GENERIC_TERMS for t in toks):
                p += 0.25
            freq_scores = [token_cluster_freq.get(t, 0) / cluster_size for t in toks]
            if freq_scores and (sum(freq_scores) / len(freq_scores)) > 0.55:
                p += 0.2
            return p

        cluster_concepts = [(i, concepts[i]) for i in indices]
        ranked_parents = []
        for idx, concept in cluster_concepts:
            centrality = float(np.dot(embeddings[idx], centroid))
            score = float(concept.score or 0.0)
            doc_freq_bonus = min(0.35, 0.06 * float(concept_doc_freq.get(concept.canonical, 0)))
            quality = score + (0.35 * centrality) + doc_freq_bonus - parent_penalty(concept.canonical)
            ranked_parents.append((quality, idx, concept, centrality))
        ranked_parents.sort(key=lambda x: x[0], reverse=True)
        dynamic_pool = max(parent_pool_size, min(12, max(2, len(cluster_concepts) // 3)))
        eligible_parent_pool = [
            item
            for item in ranked_parents
            if concept_doc_freq.get(item[2].canonical, 0) >= min_parent_doc_freq
            and not is_low_quality_label(item[2].canonical)
        ]
        if len(eligible_parent_pool) >= 2:
            parent_pool = eligible_parent_pool[: min(dynamic_pool, max(1, len(cluster_concepts) - 1))]
        else:
            parent_pool = ranked_parents[: min(dynamic_pool, max(1, len(cluster_concepts) - 1))]
        parent_indices = {p[1] for p in parent_pool}

        child_options: list[tuple[float, int, Concept, list[tuple[float, int, Concept, float]]]] = []
        for child_idx, child_concept in cluster_concepts:
            if child_idx in parent_indices:
                continue
            options: list[tuple[float, int, Concept, float]] = []
            for _rank, (_quality, parent_idx, parent_concept, parent_centrality) in enumerate(parent_pool):
                if parent_concept.canonical == child_concept.canonical:
                    continue
                sim = float(np.dot(embeddings[parent_idx], embeddings[child_idx]))
                options.append((sim, parent_idx, parent_concept, parent_centrality))
            if not options:
                continue
            options.sort(key=lambda x: x[0], reverse=True)
            child_options.append((options[0][0], child_idx, child_concept, options))

        if not child_options:
            continue

        sims = [x[0] for x in child_options]
        adaptive_threshold = max(similarity_threshold, float(np.percentile(sims, adaptive_percentile)))
        max_children = max(6, int(len(child_options) * 0.9))
        relaxed_threshold = max(0.47, adaptive_threshold - 0.07)
        parent_load: dict[int, int] = defaultdict(int)
        child_load: dict[int, int] = defaultdict(int)
        max_secondary_edges = max(1, int(len(child_options) * 0.12))
        secondary_edges_used = 0
        max_relaxed_edges = max(2, int(len(child_options) * 0.18))
        relaxed_edges_used = 0

        def lexical_overlap(a: str, b: str) -> float:
            at = set(tokenize(a))
            bt = set(tokenize(b))
            if not at or not bt:
                return 0.0
            return len(at & bt) / len(at | bt)

        child_options.sort(key=lambda x: x[0], reverse=True)
        accepted = 0
        for _best_sim, child_idx, child_concept, options in child_options:
            if accepted >= max_children:
                break
            if is_weak_single_child(child_concept.canonical):
                continue
            chosen = None
            fallback = None
            for sim, parent_idx, parent_concept, parent_centrality in options:
                if sim < adaptive_threshold:
                    continue
                if fallback is None:
                    fallback = (sim, parent_idx, parent_concept, parent_centrality)
                if parent_load[parent_idx] < max_children_per_parent:
                    chosen = (sim, parent_idx, parent_concept, parent_centrality)
                    break
            if chosen is None:
                chosen = fallback
            if chosen is None:
                continue

            sim, parent_idx, parent_concept, parent_centrality = chosen
            parent_load[parent_idx] += 1
            child_load[child_idx] += 1
            accepted += 1
            edge_key = (parent_concept.canonical, child_concept.canonical)
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)
            pairs.append({
                "hypernym": parent_concept.canonical,
                "hyponym": child_concept.canonical,
                "score": round(sim, 4),
                "evidence": {
                    "method": "embedding_clustering",
                    "cluster_id": int(cluster_id),
                    "cosine_similarity": round(sim, 4),
                    "adaptive_threshold": round(adaptive_threshold, 4),
                    "parent_centrality": round(parent_centrality, 4),
                    "parent_load": parent_load[parent_idx],
                    "parent_pool_size": len(parent_pool),
                },
            })
            # Optional secondary parent for highly-ambiguous child.
            if child_load[child_idx] == 1 and secondary_edges_used < max_secondary_edges:
                for alt_sim, alt_parent_idx, alt_parent, alt_parent_centrality in options[1:]:
                    if alt_parent.canonical == parent_concept.canonical:
                        continue
                    if alt_sim < (adaptive_threshold + 0.06):
                        continue
                    if lexical_overlap(alt_parent.canonical, child_concept.canonical) < 0.2:
                        continue
                    if parent_load[alt_parent_idx] >= (max_children_per_parent + 1):
                        continue
                    alt_key = (alt_parent.canonical, child_concept.canonical)
                    if alt_key in edge_keys:
                        continue
                    parent_load[alt_parent_idx] += 1
                    child_load[child_idx] += 1
                    secondary_edges_used += 1
                    edge_keys.add(alt_key)
                    pairs.append({
                        "hypernym": alt_parent.canonical,
                        "hyponym": child_concept.canonical,
                        "score": round(alt_sim, 4),
                        "evidence": {
                            "method": "embedding_clustering_secondary_parent",
                            "cluster_id": int(cluster_id),
                            "cosine_similarity": round(alt_sim, 4),
                            "adaptive_threshold": round(adaptive_threshold, 4),
                            "parent_centrality": round(alt_parent_centrality, 4),
                            "parent_load": parent_load[alt_parent_idx],
                            "parent_pool_size": len(parent_pool),
                        },
                    })
                    break

        # Second pass: attach still-unlinked children with slightly relaxed threshold.
        for _best_sim, child_idx, child_concept, options in child_options:
            if relaxed_edges_used >= max_relaxed_edges:
                break
            if child_load.get(child_idx, 0) > 0:
                continue
            if is_weak_single_child(child_concept.canonical):
                continue
            for sim, parent_idx, parent_concept, parent_centrality in options:
                if sim < relaxed_threshold:
                    continue
                if lexical_overlap(parent_concept.canonical, child_concept.canonical) < 0.16:
                    continue
                if parent_load[parent_idx] >= (max_children_per_parent + 2):
                    continue
                edge_key = (parent_concept.canonical, child_concept.canonical)
                if edge_key in edge_keys:
                    continue
                parent_load[parent_idx] += 1
                child_load[child_idx] += 1
                relaxed_edges_used += 1
                edge_keys.add(edge_key)
                pairs.append({
                    "hypernym": parent_concept.canonical,
                    "hyponym": child_concept.canonical,
                    "score": round(sim, 4),
                    "evidence": {
                        "method": "embedding_clustering_relaxed",
                        "cluster_id": int(cluster_id),
                        "cosine_similarity": round(sim, 4),
                        "adaptive_threshold": round(adaptive_threshold, 4),
                        "relaxed_threshold": round(relaxed_threshold, 4),
                        "parent_centrality": round(parent_centrality, 4),
                        "parent_load": parent_load[parent_idx],
                        "parent_pool_size": len(parent_pool),
                    },
                })
                break
    return pairs
