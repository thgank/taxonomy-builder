"""
Unit tests for evaluation stage — structural metrics, edge confidence.
"""
from unittest.mock import MagicMock
import uuid

from app.pipeline.evaluation import (
    _compute_structural_metrics,
    _compute_edge_confidence_stats,
)


def _make_concept(concept_id=None, collection_id=None):
    c = MagicMock()
    c.id = concept_id or uuid.uuid4()
    c.collection_id = collection_id or uuid.uuid4()
    c.canonical = f"concept_{c.id}"
    c.score = 0.5
    c.lang = "en"
    return c


def _make_edge(parent_id, child_id, score=0.7, evidence=None):
    e = MagicMock()
    e.parent_concept_id = parent_id
    e.child_concept_id = child_id
    e.score = score
    e.evidence = evidence or [{"method": "hearst"}]
    return e


class TestStructuralMetrics:
    def test_empty_concepts(self):
        result = _compute_structural_metrics([], [])
        assert result == {"error": "no_concepts"}

    def test_concepts_no_edges(self):
        concepts = [_make_concept() for _ in range(5)]
        result = _compute_structural_metrics(concepts, [])
        assert result["total_concepts"] == 5
        assert result["total_edges"] == 0
        assert result["orphan_count"] == 5
        assert result["coverage"] == 0.0

    def test_simple_tree(self):
        c1 = _make_concept()
        c2 = _make_concept()
        c3 = _make_concept()
        edges = [
            _make_edge(c1.id, c2.id),
            _make_edge(c1.id, c3.id),
        ]
        result = _compute_structural_metrics([c1, c2, c3], edges)
        assert result["total_concepts"] == 3
        assert result["total_edges"] == 2
        assert result["root_count"] == 1
        assert result["leaf_count"] == 2
        assert result["orphan_count"] == 0
        assert result["max_depth"] == 1
        assert result["coverage"] == 1.0

    def test_chain_depth(self):
        c1 = _make_concept()
        c2 = _make_concept()
        c3 = _make_concept()
        c4 = _make_concept()
        edges = [
            _make_edge(c1.id, c2.id),
            _make_edge(c2.id, c3.id),
            _make_edge(c3.id, c4.id),
        ]
        result = _compute_structural_metrics([c1, c2, c3, c4], edges)
        assert result["max_depth"] == 3
        assert result["root_count"] == 1
        assert result["leaf_count"] == 1

    def test_with_orphans(self):
        c1 = _make_concept()
        c2 = _make_concept()
        c3 = _make_concept()  # orphan
        edges = [_make_edge(c1.id, c2.id)]
        result = _compute_structural_metrics([c1, c2, c3], edges)
        assert result["orphan_count"] == 1
        assert abs(result["coverage"] - 2 / 3) < 0.01


class TestEdgeConfidenceStats:
    def test_empty(self):
        result = _compute_edge_confidence_stats([])
        assert result["count"] == 0

    def test_basic_stats(self):
        edges = [
            _make_edge(uuid.uuid4(), uuid.uuid4(), score=0.3),
            _make_edge(uuid.uuid4(), uuid.uuid4(), score=0.7),
            _make_edge(uuid.uuid4(), uuid.uuid4(), score=0.9),
        ]
        result = _compute_edge_confidence_stats(edges)
        assert result["count"] == 3
        assert result["scored"] == 3
        assert abs(result["avg_score"] - 0.6333) < 0.01
        assert result["min_score"] == 0.3
        assert result["max_score"] == 0.9

    def test_score_distribution(self):
        edges = [
            _make_edge(uuid.uuid4(), uuid.uuid4(), score=0.1),
            _make_edge(uuid.uuid4(), uuid.uuid4(), score=0.4),
            _make_edge(uuid.uuid4(), uuid.uuid4(), score=0.95),
        ]
        result = _compute_edge_confidence_stats(edges)
        assert result["score_distribution"]["0.0-0.3"] == 1
        assert result["score_distribution"]["0.3-0.5"] == 1
        assert result["score_distribution"]["0.9-1.0"] == 1

    def test_method_distribution(self):
        edges = [
            _make_edge(uuid.uuid4(), uuid.uuid4(),
                       evidence=[{"method": "hearst"}]),
            _make_edge(uuid.uuid4(), uuid.uuid4(),
                       evidence=[{"method": "embedding_clustering"}]),
            _make_edge(uuid.uuid4(), uuid.uuid4(),
                       evidence=[{"method": "hearst"}]),
        ]
        result = _compute_edge_confidence_stats(edges)
        assert result["method_distribution"]["hearst"] == 2
        assert result["method_distribution"]["embedding_clustering"] == 1
