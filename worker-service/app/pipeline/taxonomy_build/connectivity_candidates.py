from __future__ import annotations

import re

from app.pipeline.taxonomy_build.edge_filters import parent_validity_score
from app.pipeline.taxonomy_build.graph_metrics import components_with_nodes, edge_key

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def component_representative(component: set[str], concept_doc_freq: dict[str, int]) -> str:
    ranked = sorted(
        component,
        key=lambda x: (
            1 if len(TOKEN_RE.findall(x)) >= 2 else 0,
            -parent_validity_score(x, concept_doc_freq),
            -concept_doc_freq.get(x, 0),
            len(TOKEN_RE.findall(x)),
            len(x),
        ),
    )
    return ranked[0]


def fallback_connectivity_candidates(
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
    largest_anchors = sorted(
        largest,
        key=lambda x: (
            1 if len(TOKEN_RE.findall(x)) >= 2 else 0,
            -parent_validity_score(x, concept_doc_freq),
            -concept_doc_freq.get(x, 0),
            len(TOKEN_RE.findall(x)),
        ),
    )[: min(16, max(5, len(largest) // 3))]
    if not largest_anchors:
        return []

    def _lex(a: str, b: str) -> float:
        at = set(TOKEN_RE.findall(a.lower()))
        bt = set(TOKEN_RE.findall(b.lower()))
        if not at or not bt:
            return 0.0
        inter = len(at & bt)
        union = len(at | bt)
        jacc = inter / max(1, union)
        contain = 1.0 if (a.lower() in b.lower() or b.lower() in a.lower()) else 0.0
        return (0.7 * jacc) + (0.3 * contain)

    out: list[dict] = []
    used: set[tuple[str, str]] = set()
    existing = {edge_key(e) for e in edges}
    for comp in sorted((c for c in comps if c is not largest), key=len):
        rep_candidates = sorted(
            comp,
            key=lambda x: (
                1 if len(TOKEN_RE.findall(x)) >= 2 else 0,
                -parent_validity_score(x, concept_doc_freq),
                -concept_doc_freq.get(x, 0),
            ),
            reverse=True,
        )[: min(3, len(comp))]
        best_pair = None
        best_score = -1.0
        for rep in rep_candidates:
            for anc in largest_anchors:
                if rep == anc:
                    continue
                if rep in largest_set or anc not in largest_set:
                    continue
                lex = _lex(rep, anc)
                if lex > best_score:
                    best_score = lex
                    best_pair = (rep, anc, lex)
        if not best_pair:
            continue
        rep, anc, lex = best_pair
        if lex < 0.14:
            continue
        parent, child = (anc, rep)
        if parent_validity_score(parent, concept_doc_freq) < parent_validity_score(child, concept_doc_freq):
            parent, child = child, parent
        pt = TOKEN_RE.findall(parent.lower())
        ct = TOKEN_RE.findall(child.lower())
        if len(pt) == 1 and len(ct) == 1:
            continue
        key = (parent, child)
        if key in used or key in existing:
            continue
        used.add(key)
        score = max(0.56, min(0.78, 0.50 + (0.35 * lex)))
        out.append(
            {
                "hypernym": parent,
                "hyponym": child,
                "score": round(score, 4),
                "evidence": {
                    "method": "connectivity_repair_fallback",
                    "target": "largest_component",
                    "lexical_hint": round(lex, 4),
                },
            }
        )
        if len(out) >= max_links:
            break
    return out
