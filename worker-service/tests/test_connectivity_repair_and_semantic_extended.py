import math
import sys
from types import ModuleType

from app.pipeline.taxonomy_build import connectivity_repair, connectivity_semantic


def _install_fake_embeddings(monkeypatch, vectors):
    class FakeSentenceTransformer:
        def __init__(self, _model_name):
            pass

        def encode(self, rows, show_progress_bar=False, normalize_embeddings=True):
            return [vectors[row] for row in rows]

    sentence_transformers = ModuleType("sentence_transformers")
    sentence_transformers.SentenceTransformer = FakeSentenceTransformer
    numpy = ModuleType("numpy")
    numpy.dot = lambda left, right: sum(a * b for a, b in zip(left, right))
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)
    monkeypatch.setitem(sys.modules, "numpy", numpy)


def test_trim_hub_edges_reattaches_leaf_to_alternative_parent(monkeypatch):
    monkeypatch.setattr(connectivity_repair, "parent_validity_score", lambda _label, _freq: 0.9)

    pairs = [
        {"hypernym": "core energy systems", "hyponym": "battery storage", "score": 0.20, "evidence": {"method": "seed"}},
        {"hypernym": "core energy systems", "hyponym": "grid resilience network", "score": 0.91, "evidence": {"method": "seed"}},
        {"hypernym": "core energy systems", "hyponym": "energy market controls", "score": 0.88, "evidence": {"method": "seed"}},
        {"hypernym": "battery energy platform", "hyponym": "resilience hub", "score": 0.76, "evidence": {"method": "seed"}},
    ]
    concept_doc_freq = {
        "core energy systems": 12,
        "battery storage": 7,
        "grid resilience network": 6,
        "energy market controls": 6,
        "battery energy platform": 9,
        "resilience hub": 5,
    }

    kept, removed, reattached = connectivity_repair.trim_hub_edges(
        pairs,
        concept_doc_freq,
        max_outdegree=2,
    )

    kept_keys = {(edge["hypernym"], edge["hyponym"]) for edge in kept}
    assert removed == 1
    assert reattached == 1
    assert ("core energy systems", "battery storage") not in kept_keys
    assert any(parent != "core energy systems" and child == "battery storage" for parent, child in kept_keys)


def test_trim_hub_edges_respects_protected_edges():
    pairs = [
        {"hypernym": "energy systems", "hyponym": "battery storage", "score": 0.7, "evidence": {"method": "seed"}},
        {"hypernym": "energy systems", "hyponym": "grid support", "score": 0.69, "evidence": {"method": "seed"}},
    ]

    kept, removed, reattached = connectivity_repair.trim_hub_edges(
        pairs,
        {"energy systems": 10, "battery storage": 5, "grid support": 4},
        max_outdegree=1,
        protected_edge_keys={("energy systems", "battery storage"), ("energy systems", "grid support")},
    )

    assert kept == pairs
    assert removed == 0
    assert reattached == 0


def test_repair_connectivity_selects_cross_component_bridge_and_tracks_skips(monkeypatch):
    monkeypatch.setattr(connectivity_repair, "parent_validity_score", lambda label, _freq: 0.1 if label == "weak parent" else 0.9)
    monkeypatch.setattr(connectivity_repair, "is_low_quality_label", lambda label: label == "low quality node")

    current_pairs = [
        {"hypernym": "energy platform", "hyponym": "battery storage", "score": 0.8, "evidence": {"method": "seed"}},
        {"hypernym": "finance platform", "hyponym": "credit market", "score": 0.79, "evidence": {"method": "seed"}},
    ]
    candidate_pairs = [
        {"hypernym": "energy platform", "hyponym": "finance platform", "score": 0.72, "evidence": {"method": "component_bridge"}},
        {"hypernym": "energy platform", "hyponym": "battery storage", "score": 0.71, "evidence": {"method": "component_bridge"}},
        {"hypernym": "weak parent", "hyponym": "finance platform", "score": 0.75, "evidence": {"method": "component_bridge"}},
        {"hypernym": "energy platform", "hyponym": "low quality node", "score": 0.74, "evidence": {"method": "component_bridge"}},
        {"hypernym": "battery storage", "hyponym": "energy platform", "score": 0.82, "evidence": {"method": "component_bridge"}},
    ]

    repaired, stats = connectivity_repair.repair_connectivity(
        current_pairs=current_pairs,
        candidate_pairs=candidate_pairs,
        concept_labels=[
            "energy platform",
            "battery storage",
            "finance platform",
            "credit market",
            "weak parent",
            "low quality node",
        ],
        concept_doc_freq={
            "energy platform": 9,
            "battery storage": 5,
            "finance platform": 8,
            "credit market": 4,
            "weak parent": 2,
            "low quality node": 1,
        },
        target_lcr=0.9,
        max_additional_edges=2,
    )

    assert len(repaired) == 1
    assert repaired[0]["hypernym"] == "energy platform"
    assert repaired[0]["hyponym"] == "finance platform"
    assert stats["selected"] == 1
    assert stats["skipped_existing"] >= 1
    assert stats["skipped_low_parent_validity"] >= 1
    assert stats["skipped_low_quality_label"] >= 1
    assert stats["final_component_count"] == 3


def test_fallback_semantic_connectivity_candidates_uses_embedding_similarity(monkeypatch):
    _install_fake_embeddings(
        monkeypatch,
        {
            "energy platform": (1.0, 0.0),
            "battery storage unit": (0.98, 0.02),
            "grid resilience unit": (0.96, 0.04),
            "finance platform": (0.93, 0.07),
            "credit market unit": (0.90, 0.10),
        },
    )

    edges = [
        {"hypernym": "energy platform", "hyponym": "battery storage unit", "score": 0.8},
        {"hypernym": "energy platform", "hyponym": "grid resilience unit", "score": 0.78},
        {"hypernym": "finance platform", "hyponym": "credit market unit", "score": 0.76},
    ]
    candidates = connectivity_semantic.fallback_semantic_connectivity_candidates(
        edges,
        [
            "energy platform",
            "battery storage unit",
            "grid resilience unit",
            "finance platform",
            "credit market unit",
        ],
        {
            "energy platform": 10,
            "battery storage unit": 7,
            "grid resilience unit": 6,
            "finance platform": 9,
            "credit market unit": 4,
        },
        max_links=2,
    )

    assert len(candidates) >= 1
    assert all(candidate["evidence"]["method"] == "connectivity_repair_fallback" for candidate in candidates)
    assert any(candidate["evidence"]["semantic_similarity"] > 0.4 for candidate in candidates)
    assert all(0.58 <= candidate["score"] <= 0.84 for candidate in candidates)


def test_anchor_connect_components_builds_semantic_anchor_bridge(monkeypatch):
    _install_fake_embeddings(
        monkeypatch,
        {
            "energy platform": (1.0, 0.0),
            "battery storage unit": (0.99, 0.01),
            "grid resilience unit": (0.97, 0.03),
            "finance platform": (0.94, 0.06),
            "credit market unit": (0.91, 0.09),
        },
    )

    edges = [
        {"hypernym": "energy platform", "hyponym": "battery storage unit", "score": 0.8},
        {"hypernym": "energy platform", "hyponym": "grid resilience unit", "score": 0.77},
        {"hypernym": "finance platform", "hyponym": "credit market unit", "score": 0.75},
    ]
    bridges = connectivity_semantic.anchor_connect_components(
        edges,
        [
            "energy platform",
            "battery storage unit",
            "grid resilience unit",
            "finance platform",
            "credit market unit",
        ],
        {
            "energy platform": 10,
            "battery storage unit": 7,
            "grid resilience unit": 6,
            "finance platform": 9,
            "credit market unit": 4,
        },
        target_lcr=0.9,
        max_links=2,
    )

    assert len(bridges) == 1
    assert bridges[0]["evidence"]["method"] == "component_anchor_bridge"
    assert bridges[0]["evidence"]["target_lcr"] == 0.9
    assert math.isfinite(bridges[0]["score"])
