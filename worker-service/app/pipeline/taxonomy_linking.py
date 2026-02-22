from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Callable

from app.config import config
from app.pipeline.taxonomy_text import is_low_quality_label, tokenize

_DIR_PATTERNS = (
    r"\b{parent}\b.{0,80}\bsuch as\b.{0,80}\b{child}\b",
    r"\b{child}\b.{0,80}\bis (?:a|an|one of)\b.{0,80}\b{parent}\b",
    r"\b{child}\b.{0,80}\bявляется\b.{0,80}\b{parent}\b",
    r"\b{parent}\b.{0,80}\bтакие как\b.{0,80}\b{child}\b",
    r"\b{parent}\b.{0,80}\bмысалы\b.{0,80}\b{child}\b",
)


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


def _top_snippets(label: str, evidence_index: dict[str, list[dict]], top_k: int) -> list[dict]:
    return list((evidence_index or {}).get(label, []))[: max(1, top_k)]


def _directional_evidence_score(
    parent: str,
    child: str,
    parent_snippets: list[dict],
    child_snippets: list[dict],
) -> tuple[float, list[dict]]:
    parent_l = parent.lower()
    child_l = child.lower()
    parent_docs = {s.get("document_id") for s in parent_snippets if s.get("document_id")}
    child_docs = {s.get("document_id") for s in child_snippets if s.get("document_id")}
    shared_docs = parent_docs & child_docs
    shared_doc_ratio = (len(shared_docs) / max(1, len(parent_docs | child_docs))) if (parent_docs or child_docs) else 0.0

    direction_hits = 0
    contradiction_hits = 0
    snippets: list[dict] = []
    for src, bucket in (("parent", parent_snippets), ("child", child_snippets)):
        for item in bucket:
            snippet = str(item.get("snippet") or "").strip()
            if not snippet:
                continue
            snippet_l = snippet.lower()
            if parent_l not in snippet_l or child_l not in snippet_l:
                continue
            matched = False
            for pattern in _DIR_PATTERNS:
                patt = pattern.replace("{parent}", re.escape(parent_l)).replace("{child}", re.escape(child_l))
                if re.search(patt, snippet_l, flags=re.IGNORECASE):
                    direction_hits += 1
                    matched = True
                    snippets.append(
                        {
                            "source": src,
                            "document_id": item.get("document_id"),
                            "lang": item.get("lang"),
                            "snippet": snippet[: int(max(60, config.evidence_window_chars))],
                            "directional_hit": True,
                        }
                    )
                    break
            if not matched and (
                (child_l in snippet_l and f" {parent_l} " in snippet_l and " such as " in snippet_l)
                or (parent_l in snippet_l and f" {child_l} " in snippet_l and " явля" in snippet_l)
            ):
                contradiction_hits += 1

    directional = min(1.0, direction_hits / 3.0)
    contradiction_penalty = min(0.35, 0.12 * contradiction_hits)
    score = max(0.0, (0.60 * directional) + (0.40 * shared_doc_ratio) - contradiction_penalty)
    return score, snippets[: max(1, config.evidence_top_k)]


def attach_retrieval_evidence(
    edge: dict,
    evidence_index: dict[str, list[dict]] | None,
    top_k: int,
    evidence_weight: float = 0.12,
) -> dict:
    if not evidence_index:
        return edge
    parent = edge.get("hypernym", "")
    child = edge.get("hyponym", "")
    if not parent or not child:
        return edge
    parent_snippets = _top_snippets(parent, evidence_index, top_k)
    child_snippets = _top_snippets(child, evidence_index, top_k)
    if not parent_snippets and not child_snippets:
        return edge
    evidence_score, snippets = _directional_evidence_score(parent, child, parent_snippets, child_snippets)
    blended = (1.0 - evidence_weight) * float(edge.get("score", 0.0)) + (evidence_weight * evidence_score)
    edge["score"] = round(max(0.0, min(1.0, blended)), 4)
    ev = edge.get("evidence", {})
    if isinstance(ev, dict):
        ev["retrieval_evidence_score"] = round(evidence_score, 4)
        ev["retrieval_snippets"] = snippets
        ev["retrieval_snippets_count"] = len(snippets)
        edge["evidence"] = ev
    return edge


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
    evidence_index: dict[str, list[dict]] | None = None,
    evidence_top_k: int = 3,
    evidence_weight: float = 0.12,
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
        candidate = {
            "hypernym": best_parent,
            "hyponym": orphan,
            "score": round(min(0.95, best_score), 4),
            "evidence": {
                "method": "orphan_safe_link",
                "threshold": threshold,
                "similarity": round(best_score, 4),
            },
        }
        candidate = attach_retrieval_evidence(
            candidate,
            evidence_index=evidence_index,
            top_k=evidence_top_k,
            evidence_weight=evidence_weight,
        )
        added.append(candidate)
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
    max_new_children_per_parent: int = 2,
    parent_load_penalty_alpha: float = 0.06,
    evidence_index: dict[str, list[dict]] | None = None,
    evidence_top_k: int = 3,
    evidence_weight: float = 0.12,
) -> list[dict]:
    if max_links <= 0:
        return []
    max_new_children_per_parent = max(1, int(max_new_children_per_parent))
    parent_load_penalty_alpha = max(0.0, float(parent_load_penalty_alpha))
    comps = _connected_components(edges, nodes=concept_labels or [])
    if len(comps) <= 1:
        return []
    comp_idx: dict[str, int] = {}
    largest_comp_id = 0
    largest_comp_size = 0
    for i, comp in enumerate(comps):
        if len(comp) > largest_comp_size:
            largest_comp_size = len(comp)
            largest_comp_id = i
        for node in comp:
            comp_idx[node] = i

    out_degree: dict[str, int] = defaultdict(int)
    existing_pairs: set[tuple[str, str]] = set()
    for e in edges:
        out_degree[e["hypernym"]] += 1
        existing_pairs.add((e["hypernym"], e["hyponym"]))

    reps: list[str] = []
    for comp in comps:
        # Representatives: strongest nodes in component (improves bridge recall).
        ranked = sorted(
            [n for n in comp if not is_low_quality_label(n)],
            key=lambda n: (
                1 if len(tokenize(n)) >= 2 else 0,
                parent_validator(n) if parent_validator else 0.5,
                -out_degree.get(n, 0),
                -abs(len(tokenize(n)) - 2),
                -len(n),
            ),
            reverse=True,
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
    candidate_links: list[dict] = []
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
            if comp_idx.get(a) == comp_idx.get(b):
                continue
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
            if k in existing_pairs or (child, parent) in existing_pairs:
                continue
            used_pairs.add(k)
            candidate_links.append({
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
                "_bridge_meta": {
                    "cross_component": comp_idx.get(a) != comp_idx.get(b),
                    "touches_largest": (
                        comp_idx.get(a) == largest_comp_id or comp_idx.get(b) == largest_comp_id
                    ),
                    "raw_similarity": sim,
                },
            })
    candidate_links.sort(
        key=lambda e: (
            1 if e.get("_bridge_meta", {}).get("touches_largest") else 0,
            1 if e.get("_bridge_meta", {}).get("cross_component") else 0,
            float(e.get("_bridge_meta", {}).get("raw_similarity", 0.0)),
        ),
        reverse=True,
    )
    local_parent_load: dict[str, int] = defaultdict(int)
    parent_soft_cap = max(4, max_new_children_per_parent + 2)
    for edge in candidate_links:
        parent = edge["hypernym"]
        if local_parent_load[parent] >= max_new_children_per_parent:
            continue
        projected_outdegree = out_degree.get(parent, 0) + local_parent_load[parent]
        load_penalty = parent_load_penalty_alpha * max(0, projected_outdegree - parent_soft_cap)
        raw_similarity = float(edge.get("_bridge_meta", {}).get("raw_similarity", edge.get("score", 0.0)))
        adjusted_similarity = raw_similarity - load_penalty
        if adjusted_similarity < threshold:
            continue
        edge["score"] = round(min(0.92, max(0.0, adjusted_similarity)), 4)
        evidence = edge.get("evidence", {})
        if isinstance(evidence, dict):
            evidence["raw_similarity"] = round(raw_similarity, 4)
            evidence["parent_load_penalty"] = round(load_penalty, 4)
            evidence["projected_parent_outdegree"] = projected_outdegree
            evidence["similarity"] = round(adjusted_similarity, 4)
            edge["evidence"] = evidence
        edge.pop("_bridge_meta", None)
        edge = attach_retrieval_evidence(
            edge,
            evidence_index=evidence_index,
            top_k=evidence_top_k,
            evidence_weight=evidence_weight,
        )
        links.append(edge)
        local_parent_load[parent] += 1
        if len(links) >= max_links:
            break
    return links
