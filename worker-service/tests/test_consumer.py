"""
Unit tests for consumer — stage routing logic.
"""
from app.consumer import _resolve_next_routing_key, _safe_parse_message


class TestStageRouting:
    def test_full_pipeline_import_to_nlp(self):
        assert _resolve_next_routing_key("FULL_PIPELINE", "import") == "nlp"

    def test_full_pipeline_nlp_to_terms(self):
        assert _resolve_next_routing_key("FULL_PIPELINE", "nlp") == "terms"

    def test_full_pipeline_terms_to_build(self):
        assert _resolve_next_routing_key("FULL_PIPELINE", "terms") == "build"

    def test_full_pipeline_build_to_evaluate(self):
        assert _resolve_next_routing_key("FULL_PIPELINE", "build") == "evaluate"

    def test_full_pipeline_evaluate_terminal(self):
        assert _resolve_next_routing_key("FULL_PIPELINE", "evaluate") is None

    def test_single_stage_import_terminal(self):
        assert _resolve_next_routing_key("IMPORT", "import") is None

    def test_single_stage_nlp_terminal(self):
        assert _resolve_next_routing_key("NLP", "nlp") is None

    def test_single_stage_terms_terminal(self):
        assert _resolve_next_routing_key("TERMS", "terms") is None

    def test_single_stage_taxonomy_terminal(self):
        assert _resolve_next_routing_key("TAXONOMY", "build") is None

    def test_unknown_job_type_returns_none(self):
        assert _resolve_next_routing_key("UNKNOWN", "import") is None

    def test_unknown_stage_returns_none(self):
        assert _resolve_next_routing_key("FULL_PIPELINE", "nonexistent") is None


class TestSafeParseMessage:
    def test_valid_json(self):
        result = _safe_parse_message(b'{"jobId": "123"}')
        assert result == {"jobId": "123"}

    def test_invalid_json(self):
        result = _safe_parse_message(b'not json at all')
        assert result is None

    def test_empty_bytes(self):
        result = _safe_parse_message(b'')
        assert result is None

    def test_binary_garbage(self):
        result = _safe_parse_message(b'\x80\x81\x82')
        assert result is None
