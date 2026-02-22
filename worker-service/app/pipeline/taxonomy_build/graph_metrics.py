from __future__ import annotations

from collections import defaultdict


def edge_key(edge: dict) -> tuple[str, str]:
    return edge["hypernym"], edge["hyponym"]


def components_with_nodes(edges: list[dict], nodes: list[str]) -> list[set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for n in nodes:
        adjacency.setdefault(n, set())
    for e in edges:
        p = e["hypernym"]
        c = e["hyponym"]
        adjacency.setdefault(p, set()).add(c)
        adjacency.setdefault(c, set()).add(p)
    visited: set[str] = set()
    out: list[set[str]] = []
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
            out.append(comp)
    return out


def coverage_from_pairs(pairs: list[dict], concept_labels: list[str]) -> float:
    if not concept_labels:
        return 0.0
    labels: set[str] = set()
    for e in pairs:
        labels.add(e["hypernym"])
        labels.add(e["hyponym"])
    return len(labels) / max(1, len(concept_labels))


def largest_component_ratio_from_pairs(pairs: list[dict], concept_labels: list[str]) -> float:
    if not concept_labels:
        return 0.0
    comps = components_with_nodes(pairs, concept_labels)
    if not comps:
        return 0.0
    return max(len(c) for c in comps) / max(1, len(concept_labels))


def dedupe_pairs(pairs: list[dict]) -> list[dict]:
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

