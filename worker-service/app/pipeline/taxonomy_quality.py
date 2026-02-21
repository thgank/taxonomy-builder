from __future__ import annotations

from collections import defaultdict
from statistics import median

from app.pipeline.taxonomy_text import is_low_quality_label


def compute_graph_quality(edges: list[dict], total_concepts: int) -> dict[str, float]:
    if total_concepts <= 0:
        return {
            "edge_density": 0.0,
            "largest_component_ratio": 0.0,
            "hubness": 0.0,
            "lexical_noise_rate": 1.0,
        }

    labels: set[str] = set()
    for e in edges:
        labels.add(e["hypernym"])
        labels.add(e["hyponym"])

    lexical_noise_count = sum(1 for label in labels if is_low_quality_label(label))
    lexical_noise_rate = lexical_noise_count / len(labels) if labels else 0.0
    edge_density = len(edges) / total_concepts

    out_degrees: dict[str, int] = defaultdict(int)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        p = e["hypernym"]
        c = e["hyponym"]
        out_degrees[p] += 1
        adjacency[p].add(c)
        adjacency[c].add(p)

    if out_degrees:
        max_out = max(out_degrees.values())
        med_out = float(median(out_degrees.values()))
        hubness = max_out / med_out if med_out > 0 else float(max_out)
    else:
        hubness = 0.0

    visited: set[str] = set()
    largest_component = 0
    for node in adjacency.keys():
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
            stack.extend(adjacency.get(cur, set()) - visited)
        largest_component = max(largest_component, size)

    largest_component_ratio = largest_component / total_concepts
    return {
        "edge_density": round(edge_density, 4),
        "largest_component_ratio": round(largest_component_ratio, 4),
        "hubness": round(hubness, 4),
        "lexical_noise_rate": round(lexical_noise_rate, 4),
    }


def evaluate_quality_gate(report: dict[str, float], thresholds: dict[str, float]) -> list[str]:
    violations: list[str] = []
    if report["edge_density"] < thresholds["min_edge_density"]:
        violations.append(
            f"edge_density {report['edge_density']:.3f} < {thresholds['min_edge_density']:.3f}"
        )
    if report["largest_component_ratio"] < thresholds["min_largest_component_ratio"]:
        violations.append(
            f"largest_component_ratio {report['largest_component_ratio']:.3f} < "
            f"{thresholds['min_largest_component_ratio']:.3f}"
        )
    if report["hubness"] > thresholds["max_hubness"]:
        violations.append(
            f"hubness {report['hubness']:.3f} > {thresholds['max_hubness']:.3f}"
        )
    if report["lexical_noise_rate"] > thresholds["max_lexical_noise_rate"]:
        violations.append(
            f"lexical_noise_rate {report['lexical_noise_rate']:.3f} > "
            f"{thresholds['max_lexical_noise_rate']:.3f}"
        )
    return violations


def remove_cycles(edges: list[dict]) -> list[dict]:
    # Score-aware DAG projection:
    # keep strongest edges first and skip an edge if it would create a cycle.
    if not edges:
        return []

    ranked = sorted(
        edges,
        key=lambda e: float(e.get("score", 0.0)),
        reverse=True,
    )
    adjacency: dict[str, set[str]] = defaultdict(set)
    kept: list[dict] = []

    def _has_path(src: str, dst: str) -> bool:
        if src == dst:
            return True
        stack = [src]
        visited: set[str] = set()
        while stack:
            node = stack.pop()
            if node == dst:
                return True
            if node in visited:
                continue
            visited.add(node)
            stack.extend(adjacency.get(node, set()) - visited)
        return False

    for e in ranked:
        parent = e["hypernym"]
        child = e["hyponym"]
        if parent == child:
            continue
        # If child already reaches parent, this edge would close a cycle.
        if _has_path(child, parent):
            continue
        adjacency[parent].add(child)
        kept.append(e)
    return kept


def limit_depth(edges: list[dict], max_depth: int) -> list[dict]:
    parents = {e["hypernym"] for e in edges}
    children_set = {e["hyponym"] for e in edges}
    roots = parents - children_set
    if not roots:
        return edges

    parent_to_children: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        parent_to_children[e["hypernym"]].append(e["hyponym"])

    depths: dict[str, int] = {r: 0 for r in roots}
    queue = list(roots)
    while queue:
        node = queue.pop(0)
        for child in parent_to_children.get(node, []):
            if child not in depths:
                depths[child] = depths[node] + 1
                queue.append(child)
    return [e for e in edges if depths.get(e["hyponym"], 0) <= max_depth]
