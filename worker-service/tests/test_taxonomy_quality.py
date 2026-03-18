"""
Unit tests for taxonomy quality metrics and threshold evaluation.
"""
from app.pipeline.taxonomy_quality import compute_graph_quality, evaluate_quality_gate


class TestComputeGraphQuality:
    def test_reports_zeroed_metrics_for_empty_graph(self):
        result = compute_graph_quality([], total_concepts=0)

        assert result == {
            "edge_density": 0.0,
            "largest_component_ratio": 0.0,
            "hubness": 0.0,
            "lexical_noise_rate": 1.0,
        }

    def test_computes_density_component_ratio_and_hubness(self):
        edges = [
            {"hypernym": "animal", "hyponym": "dog"},
            {"hypernym": "animal", "hyponym": "cat"},
            {"hypernym": "animal", "hyponym": "fox"},
        ]

        result = compute_graph_quality(edges, total_concepts=4)

        assert result["edge_density"] == 0.75
        assert result["largest_component_ratio"] == 1.0
        assert result["hubness"] == 1.0
        assert result["lexical_noise_rate"] == 0.0


class TestEvaluateQualityGate:
    def test_returns_all_threshold_violations(self):
        report = {
            "edge_density": 0.1,
            "largest_component_ratio": 0.4,
            "hubness": 5.0,
            "lexical_noise_rate": 0.4,
        }
        thresholds = {
            "min_edge_density": 0.2,
            "min_largest_component_ratio": 0.8,
            "max_hubness": 3.0,
            "max_lexical_noise_rate": 0.2,
        }

        violations = evaluate_quality_gate(report, thresholds)

        assert len(violations) == 4
        assert any("edge_density" in item for item in violations)
        assert any("largest_component_ratio" in item for item in violations)
        assert any("hubness" in item for item in violations)
        assert any("lexical_noise_rate" in item for item in violations)
