from __future__ import annotations

import re
from collections import defaultdict

from app.pipeline.taxonomy_build.connectivity_candidates import component_representative
from app.pipeline.taxonomy_build.edge_filters import parent_validity_score
from app.pipeline.taxonomy_build.graph_metrics import components_with_nodes, edge_key

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def fallback_semantic_connectivity_candidates(
    edges: list[dict],
    concept_labels: list[str],
    concept_doc_freq: dict[str, int],
    max_links: int,
) -> list[dict]:
    if max_links <= 0:
        return []
    comps = components_with_nodes(edges, concept_labels)
    if len(comps) <= 1:
        return []
    largest = max(comps, key=len)
    largest_set = set(largest)
    out_degree: dict[str, int] = defaultdict(int)
    for edge in edges:
        out_degree[edge["hypernym"]] += 1
    largest_candidates = sorted(
        largest,
        key=lambda x: (
            1 if len(TOKEN_RE.findall(x)) >= 2 else 0,
            parent_validity_score(x, concept_doc_freq),
            concept_doc_freq.get(x, 0),
            -out_degree.get(x, 0),
            -abs(len(TOKEN_RE.findall(x)) - 2),
        ),
        reverse=True,
    )[: min(30, max(10, len(largest) // 2))]
    if not largest_candidates:
        return []

    reps: list[str] = []
    for comp in sorted((c for c in comps if c is not largest), key=len):
        ranked = sorted(
            comp,
            key=lambda x: (
                1 if len(TOKEN_RE.findall(x)) >= 2 else 0,
                parent_validity_score(x, concept_doc_freq),
                concept_doc_freq.get(x, 0),
                -out_degree.get(x, 0),
            ),
            reverse=True,
        )
        reps.extend(ranked[: min(2, len(ranked))])
    reps = list(dict.fromkeys(reps))
    if not reps:
        return []

    rows = list(dict.fromkeys(reps + largest_candidates))
    semantic_scores: dict[tuple[str, str], float] = {}
    if len(rows) >= 2:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            vectors = model.encode(rows, show_progress_bar=False, normalize_embeddings=True)
            idx = {rows[i]: i for i in range(len(rows))}
            for r in reps:
                for a in largest_candidates:
                    semantic_scores[(r, a)] = float(np.dot(vectors[idx[r]], vectors[idx[a]]))
        except Exception:
            semantic_scores = {}

    existing = {edge_key(e) for e in edges}
    used: set[tuple[str, str]] = set()
    out: list[dict] = []
    for rep in reps:
        best_anchor = None
        best_combined = -1.0
        best_sem = 0.0
        best_lex = 0.0
        rep_t = set(TOKEN_RE.findall(rep.lower()))
        for anchor in largest_candidates:
            if rep == anchor:
                continue
            sem = semantic_scores.get((rep, anchor), 0.0)
            anc_t = set(TOKEN_RE.findall(anchor.lower()))
            lex = (len(rep_t & anc_t) / max(1, len(rep_t | anc_t))) if rep_t and anc_t else 0.0
            hub_penalty = 0.03 * max(0, out_degree.get(anchor, 0) - 4)
            combined = (0.82 * sem) + (0.18 * lex) - hub_penalty
            if combined > best_combined:
                best_anchor = anchor
                best_combined = combined
                best_sem = sem
                best_lex = lex
        if not best_anchor:
            continue
        if best_sem < 0.40 and best_combined < 0.52:
            continue
        parent, child = (best_anchor, rep)
        if parent_validity_score(parent, concept_doc_freq) < parent_validity_score(child, concept_doc_freq):
            parent, child = child, parent
        if parent in largest_set and child in largest_set:
            continue
        key = (parent, child)
        if key in existing or key in used:
            continue
        pt = TOKEN_RE.findall(parent.lower())
        ct = TOKEN_RE.findall(child.lower())
        if len(pt) == 1 and len(ct) == 1:
            continue
        used.add(key)
        score = max(0.58, min(0.84, (0.55 * best_combined) + (0.35 * best_sem) + (0.10 * best_lex)))
        out.append(
            {
                "hypernym": parent,
                "hyponym": child,
                "score": round(score, 4),
                "evidence": {
                    "method": "connectivity_repair_fallback",
                    "target": "largest_component_semantic",
                    "similarity": round(best_combined, 4),
                    "semantic_similarity": round(best_sem, 4),
                    "lexical_similarity": round(best_lex, 4),
                },
            }
        )
        if len(out) >= max_links:
            break
    return out


def anchor_connect_components(
    edges: list[dict],
    concept_labels: list[str],
    concept_doc_freq: dict[str, int],
    target_lcr: float,
    max_links: int,
) -> list[dict]:
    if max_links <= 0:
        return []
    comps = components_with_nodes(edges, concept_labels)
    if len(comps) <= 1:
        return []
    total = max(1, len(concept_labels))
    largest = max(comps, key=len)
    if (len(largest) / total) >= target_lcr:
        return []
    out_degree: dict[str, int] = defaultdict(int)
    for edge in edges:
        out_degree[edge["hypernym"]] += 1

    reps = [component_representative(c, concept_doc_freq) for c in comps if c is not largest]
    base_anchors = sorted(
        largest,
        key=lambda x: (
            1 if len(TOKEN_RE.findall(x)) >= 2 else 0,
            parent_validity_score(x, concept_doc_freq),
            concept_doc_freq.get(x, 0),
            -out_degree.get(x, 0),
            -abs(len(TOKEN_RE.findall(x)) - 2),
        ),
        reverse=True,
    )[: min(20, max(8, len(largest) // 2))]
    anchors = list(base_anchors[: min(12, max(4, len(largest) // 3))])
    if not anchors:
        return []

    semantic_scores: dict[tuple[str, str], float] = {}
    rows = list(dict.fromkeys(reps + base_anchors))
    if len(rows) >= 2:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            vectors = model.encode(rows, show_progress_bar=False, normalize_embeddings=True)
            idx = {rows[i]: i for i in range(len(rows))}
            for r in reps:
                for a in base_anchors:
                    semantic_scores[(r, a)] = float(np.dot(vectors[idx[r]], vectors[idx[a]]))
        except Exception:
            semantic_scores = {}

    boundary_candidates: list[tuple[float, str]] = []
    for anchor in base_anchors:
        best_to_reps = max((semantic_scores.get((r, anchor), 0.0) for r in reps), default=0.0)
        boundary_candidates.append((best_to_reps, anchor))
    boundary_candidates.sort(reverse=True)
    for _sim, anchor in boundary_candidates[: min(6, len(boundary_candidates))]:
        if anchor not in anchors:
            anchors.append(anchor)

    out: list[dict] = []
    used: set[tuple[str, str]] = set()
    for comp in sorted((c for c in comps if c is not largest), key=len):
        rep = component_representative(comp, concept_doc_freq)
        best = None
        best_score = -1.0
        best_sem = 0.0
        best_lex = 0.0
        for anchor in anchors:
            if rep == anchor:
                continue
            sem = semantic_scores.get((rep, anchor), 0.0)
            rep_t = set(TOKEN_RE.findall(rep.lower()))
            anc_t = set(TOKEN_RE.findall(anchor.lower()))
            lex = (len(rep_t & anc_t) / max(1, len(rep_t | anc_t))) if rep_t and anc_t else 0.0
            hub_penalty = 0.04 * max(0, out_degree.get(anchor, 0) - 4)
            score = (0.7 * sem) + (0.3 * lex) - hub_penalty
            if score > best_score:
                best_score = score
                best = anchor
                best_sem = sem
                best_lex = lex
        if not best:
            continue
        parent, child = (best, rep)
        if parent_validity_score(parent, concept_doc_freq) < parent_validity_score(child, concept_doc_freq):
            parent, child = child, parent
        if parent == child:
            continue
        key = (parent, child)
        if key in used:
            continue
        used.add(key)
        out.append(
            {
                "hypernym": parent,
                "hyponym": child,
                "score": round(max(0.55, min(0.9, best_score)), 4),
                "evidence": {
                    "method": "component_anchor_bridge",
                    "similarity": round(max(0.0, best_score), 4),
                    "semantic_similarity": round(max(0.0, best_sem), 4),
                    "lexical_similarity": round(max(0.0, best_lex), 4),
                    "target_lcr": round(target_lcr, 4),
                },
            }
        )
        if len(out) >= max_links:
            break
    return out
