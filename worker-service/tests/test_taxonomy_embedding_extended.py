from types import ModuleType, SimpleNamespace
import builtins
import sys

from app.pipeline import taxonomy_embedding


def _concept(label, score):
    return SimpleNamespace(canonical=label, score=score)


def test_build_embedding_hierarchy_returns_empty_when_transformers_missing(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = taxonomy_embedding.build_embedding_hierarchy(
        [_concept("energy", 0.9), _concept("battery storage", 0.8), _concept("microgrid", 0.7)],
    )

    assert result == []


def test_build_embedding_hierarchy_generates_cluster_edges_with_hdbscan(monkeypatch):
    sentence_transformers = ModuleType("sentence_transformers")
    hdbscan = ModuleType("hdbscan")

    class FakeModel:
        def encode(self, terms, show_progress_bar=False, normalize_embeddings=True):
            mapping = {
                "energy system": [1.0, 0.0],
                "battery storage": [0.96, 0.04],
                "grid battery": [0.94, 0.06],
                "microgrid": [0.92, 0.08],
            }
            return [mapping[term] for term in terms]

    class FakeClusterer:
        def __init__(self, **_kwargs):
            pass

        def fit_predict(self, _embeddings):
            return [0, 0, 0, 0]

    sentence_transformers.SentenceTransformer = lambda _name: FakeModel()
    hdbscan.HDBSCAN = FakeClusterer
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)
    monkeypatch.setitem(sys.modules, "hdbscan", hdbscan)
    monkeypatch.setattr(taxonomy_embedding, "is_low_quality_label", lambda _label: False)

    edges = taxonomy_embedding.build_embedding_hierarchy(
        [
            _concept("energy system", 0.95),
            _concept("battery storage", 0.8),
            _concept("grid battery", 0.79),
            _concept("microgrid", 0.77),
        ],
        similarity_threshold=0.5,
        parent_pool_size=2,
        max_children_per_parent=2,
        adaptive_percentile=40,
        concept_doc_freq={"energy system": 8, "battery storage": 4, "grid battery": 4, "microgrid": 3},
        min_parent_doc_freq=1,
    )

    assert edges
    assert any(edge["evidence"]["method"] == "embedding_clustering" for edge in edges)
    assert all("adaptive_threshold" in edge["evidence"] for edge in edges)


def test_build_embedding_hierarchy_falls_back_to_kmeans(monkeypatch):
    sentence_transformers = ModuleType("sentence_transformers")
    sklearn = ModuleType("sklearn")
    sklearn_cluster = ModuleType("sklearn.cluster")

    class FakeModel:
        def encode(self, terms, show_progress_bar=False, normalize_embeddings=True):
            mapping = {
                "energy platform": [1.0, 0.0],
                "battery platform": [0.97, 0.03],
                "credit platform": [0.0, 1.0],
                "loan platform": [0.02, 0.98],
                "grid battery": [0.95, 0.05],
            }
            return [mapping[term] for term in terms]

    class FakeKMeans:
        def __init__(self, **_kwargs):
            pass

        def fit_predict(self, _embeddings):
            return [0, 0, 1, 1, 0]

    sentence_transformers.SentenceTransformer = lambda _name: FakeModel()
    sklearn_cluster.KMeans = FakeKMeans
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)
    monkeypatch.setitem(sys.modules, "sklearn", sklearn)
    monkeypatch.setitem(sys.modules, "sklearn.cluster", sklearn_cluster)
    monkeypatch.delitem(sys.modules, "hdbscan", raising=False)
    monkeypatch.setattr(taxonomy_embedding, "is_low_quality_label", lambda _label: False)

    edges = taxonomy_embedding.build_embedding_hierarchy(
        [
            _concept("energy platform", 0.95),
            _concept("battery platform", 0.86),
            _concept("credit platform", 0.82),
            _concept("loan platform", 0.81),
            _concept("grid battery", 0.78),
        ],
        similarity_threshold=0.45,
        parent_pool_size=2,
        max_children_per_parent=2,
        adaptive_percentile=30,
        concept_doc_freq={
            "energy platform": 7,
            "battery platform": 5,
            "credit platform": 6,
            "loan platform": 5,
            "grid battery": 4,
        },
        min_parent_doc_freq=1,
    )

    assert edges
    assert any(edge["hypernym"] == "energy platform" for edge in edges)
