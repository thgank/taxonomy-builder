from types import SimpleNamespace
from unittest.mock import MagicMock

from app.pipeline import taxonomy_builder


def _ctx(global_selector_enabled=True, enforce_quality_gate=False):
    return SimpleNamespace(
        concepts=["concept-1"],
        session=MagicMock(),
        job_id="job-1",
        taxonomy_version_id="tax-1",
        threshold_profile_id=None,
        settings=SimpleNamespace(
            global_selector_enabled=global_selector_enabled,
            enforce_quality_gate=enforce_quality_gate,
        ),
    )


def test_handle_build_finalizes_empty_when_no_concepts(monkeypatch):
    ctx = _ctx()
    finalize_calls = []
    monkeypatch.setattr(taxonomy_builder, "load_build_context", lambda *args, **kwargs: SimpleNamespace(concepts=[]))
    monkeypatch.setattr(taxonomy_builder, "finalize_empty", lambda context, message: finalize_calls.append(message))
    monkeypatch.setattr(taxonomy_builder, "update_job_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "update_taxonomy_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "add_job_event", lambda *args, **kwargs: None)

    taxonomy_builder.handle_build(MagicMock(), {"jobId": "job-1", "collectionId": "col-1", "taxonomyVersionId": "tax-1"})

    assert finalize_calls == ["No concepts found — skipping build"]


def test_handle_build_finalizes_empty_when_no_pairs(monkeypatch):
    ctx = _ctx()
    finalize_calls = []
    monkeypatch.setattr(taxonomy_builder, "load_build_context", lambda *args, **kwargs: ctx)
    monkeypatch.setattr(taxonomy_builder, "build_all_relation_candidates", lambda context: [])
    monkeypatch.setattr(taxonomy_builder, "is_job_cancelled", lambda *args, **kwargs: False)
    monkeypatch.setattr(taxonomy_builder, "finalize_empty", lambda context, message: finalize_calls.append(message))
    monkeypatch.setattr(taxonomy_builder, "update_job_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "update_taxonomy_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "add_job_event", lambda *args, **kwargs: None)

    taxonomy_builder.handle_build(MagicMock(), {"jobId": "job-1", "collectionId": "col-1", "taxonomyVersionId": "tax-1"})

    assert finalize_calls == ["No taxonomy relations found"]


def test_handle_build_marks_failed_when_quality_gate_is_enforced(monkeypatch):
    ctx = _ctx(global_selector_enabled=False, enforce_quality_gate=True)
    state = SimpleNamespace(candidate_logs=[], ranker_enabled=False, unique_pairs=[("a", "b")])
    statuses = []
    monkeypatch.setattr(taxonomy_builder, "load_build_context", lambda *args, **kwargs: ctx)
    monkeypatch.setattr(taxonomy_builder, "build_all_relation_candidates", lambda context: [("a", "b")])
    monkeypatch.setattr(taxonomy_builder, "build_initial_state", lambda context, all_pairs: state)
    monkeypatch.setattr(taxonomy_builder, "apply_connectivity_expansion", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "run_postprocess_and_recovery", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "persist_edge_candidates", lambda *args, **kwargs: 0)
    monkeypatch.setattr(taxonomy_builder, "evaluate_quality_gate_and_hubness", lambda *args, **kwargs: ({}, ["low coverage"]))
    monkeypatch.setattr(taxonomy_builder, "update_job_status", lambda session, job_id, status, **kwargs: statuses.append((status, kwargs)))
    monkeypatch.setattr(taxonomy_builder, "update_taxonomy_status", lambda session, tax_id, status: statuses.append((status, {})))
    monkeypatch.setattr(taxonomy_builder, "add_job_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "is_job_cancelled", lambda *args, **kwargs: False)

    taxonomy_builder.handle_build(MagicMock(), {"jobId": "job-1", "collectionId": "col-1", "taxonomyVersionId": "tax-1"})

    assert ("FAILED", {}) in statuses
    assert any(status == "FAILED" and kwargs.get("error_message") == "Quality gate failed: low coverage" for status, kwargs in statuses)


def test_handle_build_successfully_persists_edges_and_finalizes(monkeypatch):
    ctx = _ctx(global_selector_enabled=True, enforce_quality_gate=False)
    state = SimpleNamespace(candidate_logs=["candidate"], ranker_enabled=True, unique_pairs=[("parent", "child")], selector_stats=None)
    events = []
    finalize_success_calls = []
    monkeypatch.setattr(taxonomy_builder, "load_build_context", lambda *args, **kwargs: ctx)
    monkeypatch.setattr(taxonomy_builder, "build_all_relation_candidates", lambda context: [("parent", "child")])
    monkeypatch.setattr(taxonomy_builder, "build_initial_state", lambda context, all_pairs: state)
    monkeypatch.setattr(taxonomy_builder, "apply_connectivity_expansion", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "run_postprocess_and_recovery", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "apply_global_edge_selector", lambda context, current_state: {"pool_size": 4, "selected": 1, "final_lcr": 0.91, "fallback": False})
    monkeypatch.setattr(taxonomy_builder, "persist_edge_candidates", lambda context, logs: len(logs))
    monkeypatch.setattr(taxonomy_builder, "evaluate_quality_gate_and_hubness", lambda *args, **kwargs: ({}, []))
    monkeypatch.setattr(taxonomy_builder, "persist_taxonomy_edges", lambda context, pairs: len(pairs))
    monkeypatch.setattr(taxonomy_builder, "finalize_success", lambda context, stored: finalize_success_calls.append(stored))
    monkeypatch.setattr(taxonomy_builder, "update_job_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "update_taxonomy_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(taxonomy_builder, "add_job_event", lambda session, job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(taxonomy_builder, "is_job_cancelled", lambda *args, **kwargs: False)

    taxonomy_builder.handle_build(MagicMock(), {"jobId": "job-1", "collectionId": "col-1", "taxonomyVersionId": "tax-1"})

    assert state.selector_stats["selected"] == 1
    assert finalize_success_calls == [1]
    assert any("Global selector:" in message for _level, message in events)
    assert any("After post-processing: 1 edges" == message for _level, message in events)
