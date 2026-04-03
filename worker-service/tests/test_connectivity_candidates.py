from app.pipeline.taxonomy_build import connectivity_candidates


def test_component_representative_prefers_informative_multi_token_node():
    rep = connectivity_candidates.component_representative(
        {"energy", "energy system", "grid"},
        {"energy": 5, "energy system": 6, "grid": 3},
    )

    assert rep == "energy system"


def test_fallback_connectivity_candidates_links_small_components_to_largest():
    edges = [
        {"hypernym": "energy system", "hyponym": "battery energy system", "score": 0.8},
        {"hypernym": "finance system", "hyponym": "credit finance system", "score": 0.76},
    ]
    labels = ["energy system", "battery energy system", "finance system", "credit finance system"]
    concept_doc_freq = {
        "energy system": 7,
        "battery energy system": 4,
        "finance system": 6,
        "credit finance system": 3,
    }

    candidates = connectivity_candidates.fallback_connectivity_candidates(edges, labels, concept_doc_freq, max_links=2)

    assert len(candidates) == 1
    assert candidates[0]["evidence"]["method"] == "connectivity_repair_fallback"
    assert candidates[0]["score"] >= 0.56


def test_fallback_connectivity_candidates_returns_empty_for_single_component():
    candidates = connectivity_candidates.fallback_connectivity_candidates(
        [{"hypernym": "energy system", "hyponym": "battery energy system", "score": 0.8}],
        ["energy system", "battery energy system"],
        {"energy system": 7, "battery energy system": 4},
        max_links=2,
    )

    assert candidates == []
