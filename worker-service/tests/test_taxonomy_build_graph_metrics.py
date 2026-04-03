from app.pipeline.taxonomy_build.graph_metrics import (
    components_with_nodes,
    coverage_from_pairs,
    dedupe_pairs,
    edge_key,
    largest_component_ratio_from_pairs,
)


def test_edge_key_and_components_with_nodes_cover_isolated_nodes():
    pairs = [{"hypernym": "energy", "hyponym": "battery"}]

    assert edge_key(pairs[0]) == ("energy", "battery")
    components = components_with_nodes(pairs, ["energy", "battery", "market"])

    assert {frozenset(component) for component in components} == {
        frozenset({"energy", "battery"}),
        frozenset({"market"}),
    }


def test_coverage_and_largest_component_ratio_are_computed_from_pairs():
    pairs = [
        {"hypernym": "energy", "hyponym": "battery"},
        {"hypernym": "energy", "hyponym": "grid"},
    ]

    assert coverage_from_pairs(pairs, ["energy", "battery", "grid", "market"]) == 0.75
    assert largest_component_ratio_from_pairs(pairs, ["energy", "battery", "grid", "market"]) == 0.75


def test_dedupe_pairs_merges_evidence_and_keeps_max_score():
    merged = dedupe_pairs(
        [
            {"hypernym": "energy", "hyponym": "battery", "score": 0.7, "evidence": [{"method": "hearst"}]},
            {"hypernym": "energy", "hyponym": "battery", "score": 0.9, "evidence": {"method": "embedding"}},
        ]
    )

    assert len(merged) == 1
    assert merged[0]["score"] == 0.9
    assert len(merged[0]["evidence"]) == 2
