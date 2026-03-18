"""
Unit tests for taxonomy builder — Hearst patterns, cycle removal.
"""
from app.pipeline.taxonomy_quality import limit_depth, remove_cycles
from app.pipeline.taxonomy_text import split_enumeration


class TestSplitEnumeration:
    def test_comma_and(self):
        result = split_enumeration("cats, dogs and fish")
        assert "cats" in result
        assert "dogs" in result
        assert "fish" in result

    def test_simple(self):
        result = split_enumeration("alpha")
        assert result == ["alpha"]


class TestRemoveCycles:
    def test_no_cycle(self):
        edges = [
            {"hypernym": "animal", "hyponym": "dog", "score": 0.9},
            {"hypernym": "animal", "hyponym": "cat", "score": 0.8},
        ]
        result = remove_cycles(edges)
        assert len(result) == 2

    def test_with_cycle(self):
        edges = [
            {"hypernym": "a", "hyponym": "b", "score": 0.9},
            {"hypernym": "b", "hyponym": "c", "score": 0.8},
            {"hypernym": "c", "hyponym": "a", "score": 0.5},  # cycle
        ]
        result = remove_cycles(edges)
        # Should remove one edge to break cycle
        assert len(result) < 3


class TestLimitDepth:
    def test_within_limit(self):
        edges = [
            {"hypernym": "root", "hyponym": "child1", "score": 1.0},
            {"hypernym": "child1", "hyponym": "grandchild", "score": 0.8},
        ]
        result = limit_depth(edges, max_depth=5)
        assert len(result) == 2

    def test_beyond_limit(self):
        edges = [
            {"hypernym": "a", "hyponym": "b", "score": 1.0},
            {"hypernym": "b", "hyponym": "c", "score": 1.0},
            {"hypernym": "c", "hyponym": "d", "score": 1.0},
        ]
        result = limit_depth(edges, max_depth=2)
        # d is at depth 3, should be removed
        assert len(result) <= 2
