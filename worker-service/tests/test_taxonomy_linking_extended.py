from types import ModuleType, SimpleNamespace
import sys

from app.pipeline import taxonomy_linking


def test_attach_retrieval_evidence_blends_directional_snippets():
    edge = {
        "hypernym": "energy system",
        "hyponym": "battery storage",
        "score": 0.7,
        "evidence": {"method": "orphan_safe_link"},
    }
    evidence_index = {
        "energy system": [
            {"document_id": "doc-1", "lang": "en", "snippet": "Energy system such as battery storage improves resilience."},
        ],
        "battery storage": [
            {"document_id": "doc-1", "lang": "en", "snippet": "Battery storage is a energy system component."},
        ],
    }

    updated = taxonomy_linking.attach_retrieval_evidence(edge, evidence_index=evidence_index, top_k=2, evidence_weight=0.2)

    assert updated["score"] > 0.7
    assert updated["evidence"]["retrieval_evidence_score"] > 0.0
    assert updated["evidence"]["retrieval_snippets_count"] >= 1


def test_safe_link_orphans_adds_candidates_with_parent_load_limits():
    edges = [
        {"hypernym": "energy system", "hyponym": "microgrid", "score": 0.7, "evidence": {"method": "seed"}},
        {"hypernym": "energy system", "hyponym": "solar storage", "score": 0.69, "evidence": {"method": "seed"}},
    ]
    labels = ["energy system", "microgrid", "solar storage", "battery storage", "grid battery"]
    scores = {"battery storage": 0.8, "grid battery": 0.85}
    freqs = {"battery storage": 3, "grid battery": 4}

    added = taxonomy_linking.safe_link_orphans(
        edges,
        labels,
        threshold=0.15,
        max_links=2,
        parent_validator=lambda label: 0.8 if label == "energy system" else 0.4,
        concept_doc_freq=freqs,
        concept_scores=scores,
        evidence_index={
            "energy system": [{"document_id": "doc-1", "lang": "en", "snippet": "energy system such as battery storage"}],
            "battery storage": [{"document_id": "doc-1", "lang": "en", "snippet": "battery storage is a energy system asset"}],
        },
    )

    assert len(added) >= 1
    assert all(edge["hypernym"] == "energy system" for edge in added)
    assert all(edge["evidence"]["method"] == "orphan_safe_link" for edge in added)


def test_bridge_components_uses_semantic_similarity_and_parent_penalties(monkeypatch):
    sentence_transformers = ModuleType("sentence_transformers")

    class FakeModel:
        def encode(self, labels, show_progress_bar=False, normalize_embeddings=True):
            mapping = {
                "energy platform": [1.0, 0.0],
                "battery platform": [0.95, 0.05],
                "finance platform": [0.92, 0.08],
                "credit platform": [0.88, 0.12],
            }
            return [mapping[label] for label in labels]

    sentence_transformers.SentenceTransformer = lambda _name: FakeModel()
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)

    links = taxonomy_linking.bridge_components(
        edges=[
            {"hypernym": "energy platform", "hyponym": "battery platform", "score": 0.8, "evidence": {"method": "seed"}},
            {"hypernym": "finance platform", "hyponym": "credit platform", "score": 0.78, "evidence": {"method": "seed"}},
        ],
        threshold=0.2,
        max_links=2,
        concept_labels=["energy platform", "battery platform", "finance platform", "credit platform"],
        parent_validator=lambda label: 0.82 if "platform" in label else 0.51,
        min_lexical_similarity=0.1,
        min_semantic_similarity=0.1,
        max_new_children_per_parent=1,
        parent_load_penalty_alpha=0.01,
        evidence_index={
            "energy platform": [{"document_id": "doc-1", "lang": "en", "snippet": "energy platform such as finance platform"}],
            "finance platform": [{"document_id": "doc-1", "lang": "en", "snippet": "finance platform is an energy platform peer"}],
        },
    )

    assert len(links) >= 1
    assert all(link["evidence"]["method"] == "component_bridge" for link in links)
    assert all("raw_similarity" in link["evidence"] for link in links)
    assert all("_bridge_meta" not in link for link in links)


def test_connected_components_returns_disconnected_groups():
    comps = taxonomy_linking._connected_components(
        [{"hypernym": "a", "hyponym": "b"}, {"hypernym": "c", "hyponym": "d"}],
        nodes=["a", "b", "c", "d", "e"],
    )

    assert any({"a", "b"} == comp for comp in comps)
    assert any({"c", "d"} == comp for comp in comps)
    assert any({"e"} == comp for comp in comps)
