from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from typing import Callable

from app.config import config
from app.pipeline.taxonomy_text import is_low_quality_label, tokenize


def _label_similarity(a: str, b: str) -> float:
    at = set(tokenize(a))
    bt = set(tokenize(b))
    if not at or not bt:
        return 0.0
    inter = len(at & bt)
    union = len(at | bt)
    jaccard = inter / union if union else 0.0
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    contain = 1.0 if (a.lower() in b.lower() or b.lower() in a.lower()) else 0.0
    return (0.45 * jaccard) + (0.40 * seq) + (0.15 * contain)


def safe_link_orphans(
    edges: list[dict],
    concept_labels: list[str],
    threshold: float,
    max_links: int,
    parent_validator: Callable[[str], float] | None = None,
    concept_doc_freq: dict[str, int] | None = None,
    concept_scores: dict[str, float] | None = None,
    min_orphan_doc_freq: int = 2,
    min_orphan_score: float = 0.25,
) -> list[dict]:
    if not concept_labels or max_links <= 0:
        return []
    if concept_doc_freq is None:
        concept_doc_freq = {}
    if concept_scores is None:
        concept_scores = {}

    connected: set[str] = set()
    parent_counts: dict[str, int] = defaultdict(int)
    for e in edges:
        p = e["hypernym"]
        c = e["hyponym"]
        connected.add(p)
        connected.add(c)
        parent_counts[p] += 1

    orphans = [
        c for c in concept_labels
        if c not in connected
        and not is_low_quality_label(c)
        and concept_doc_freq.get(c, 0) >= min_orphan_doc_freq
        and concept_scores.get(c, 0.0) >= min_orphan_score
    ]
    parent_candidates = [p for p in parent_counts.keys() if not is_low_quality_label(p)]
    if not parent_candidates:
        parent_candidates = [c for c in connected if not is_low_quality_label(c)]
    if not parent_candidates:
        return []

    added: list[dict] = []
    local_parent_load: dict[str, int] = defaultdict(int)
    max_per_parent = 3

    for orphan in orphans:
        best_parent = None
        best_score = 0.0
        orphan_len = max(1, len(tokenize(orphan)))
        for parent in parent_candidates:
            if parent == orphan:
                continue
            if parent_validator and parent_validator(parent) < 0.45:
                continue
            sim = _label_similarity(parent, orphan)
            if sim < threshold:
                continue
            parent_len = max(1, len(tokenize(parent)))
            generality_bonus = 0.05 if parent_len <= orphan_len else 0.0
            over_hub_penalty = 0.03 * max(0, parent_counts.get(parent, 0) + local_parent_load[parent] - 4)
            score = sim + generality_bonus - over_hub_penalty
            if score > best_score:
                best_score = score
                best_parent = parent

        if not best_parent:
            continue
        if local_parent_load[best_parent] >= max_per_parent:
            continue

        local_parent_load[best_parent] += 1
        added.append({
            "hypernym": best_parent,
            "hyponym": orphan,
            "score": round(min(0.95, best_score), 4),
            "evidence": {
                "method": "orphan_safe_link",
                "threshold": threshold,
                "similarity": round(best_score, 4),
            },
        })
        if len(added) >= max_links:
            break

    return added


def _connected_components(edges: list[dict], nodes: list[str] | None = None) -> list[set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        p = e["hypernym"]
        c = e["hyponym"]
        adjacency[p].add(c)
        adjacency[c].add(p)
    if nodes:
        for n in nodes:
            adjacency.setdefault(n, set())

    visited: set[str] = set()
    comps: list[set[str]] = []
    for node in adjacency.keys():
        if node in visited:
            continue
        stack = [node]
        comp: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            stack.extend(adjacency.get(cur, set()) - visited)
        if comp:
            comps.append(comp)
    return comps


def bridge_components(
    edges: list[dict],
    threshold: float,
    max_links: int,
    concept_labels: list[str] | None = None,
    parent_validator: Callable[[str], float] | None = None,
    min_lexical_similarity: float | None = None,
    min_semantic_similarity: float | None = None,
) -> list[dict]:
    if max_links <= 0:
        return []
    comps = _connected_components(edges, nodes=concept_labels or [])
    if len(comps) <= 1:
        return []

    out_degree: dict[str, int] = defaultdict(int)
    for e in edges:
        out_degree[e["hypernym"]] += 1

    reps: list[str] = []
    for comp in comps:
        # Representatives: strongest nodes in component (improves bridge recall).
        ranked = sorted(
            [n for n in comp if not is_low_quality_label(n)],
            key=lambda n: (-out_degree.get(n, 0), len(tokenize(n)), len(n)),
        )
        if not ranked:
            continue
        reps.extend(ranked[: min(3, len(ranked))])

    semantic_scores: dict[tuple[str, str], float] = {}
    unique_reps = list(dict.fromkeys(reps))
    if len(unique_reps) >= 2:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            vectors = model.encode(unique_reps, show_progress_bar=False, normalize_embeddings=True)
            for i in range(len(unique_reps)):
                for j in range(i + 1, len(unique_reps)):
                    sim = float(np.dot(vectors[i], vectors[j]))
                    semantic_scores[(unique_reps[i], unique_reps[j])] = sim
                    semantic_scores[(unique_reps[j], unique_reps[i])] = sim
        except Exception:
            semantic_scores = {}

    links: list[dict] = []
    used_pairs: set[tuple[str, str]] = set()
    lexical_floor = (
        float(min_lexical_similarity)
        if min_lexical_similarity is not None
        else float(config.min_bridge_lexical_similarity)
    )
    semantic_floor = (
        float(min_semantic_similarity)
        if min_semantic_similarity is not None
        else float(config.min_bridge_semantic_similarity)
    )
    for i in range(len(reps)):
        for j in range(i + 1, len(reps)):
            a = reps[i]
            b = reps[j]
            lexical_sim = _label_similarity(a, b)
            semantic_sim = semantic_scores.get((a, b), 0.0)
            sim = max(lexical_sim, (0.35 * lexical_sim) + (0.65 * semantic_sim))
            if sim < threshold:
                continue
            if lexical_sim < lexical_floor:
                continue
            if semantic_sim < semantic_floor:
                continue
            # Orient edge: prefer label with higher parent-validity, fallback to shorter term.
            if parent_validator:
                a_valid = parent_validator(a)
                b_valid = parent_validator(b)
                if abs(a_valid - b_valid) >= 0.08:
                    parent, child = (a, b) if a_valid >= b_valid else (b, a)
                else:
                    parent, child = (a, b) if len(tokenize(a)) <= len(tokenize(b)) else (b, a)
                if parent_validator(parent) < 0.40:
                    continue
            else:
                parent, child = (a, b) if len(tokenize(a)) <= len(tokenize(b)) else (b, a)
            if parent == child:
                continue
            k = (parent, child)
            if k in used_pairs:
                continue
            used_pairs.add(k)
            links.append({
                "hypernym": parent,
                "hyponym": child,
                "score": round(min(0.92, sim), 4),
                "evidence": {
                    "method": "component_bridge",
                    "threshold": threshold,
                    "similarity": round(sim, 4),
                    "lexical_similarity": round(lexical_sim, 4),
                    "semantic_similarity": round(semantic_sim, 4),
                },
            })
            if len(links) >= max_links:
                return links
    return links
