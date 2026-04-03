from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

from app.pipeline.taxonomy_build import build_context


def _query_first(result):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = result
    return query


def _query_all(result):
    query = MagicMock()
    query.filter.return_value = query
    query.join.return_value = query
    query.all.return_value = result
    return query


def test_load_threshold_profile_prefers_collection_profile_and_falls_back_to_global(monkeypatch):
    collection_profile = SimpleNamespace(id=uuid.uuid4(), profile={"min_edge_accept_score": 0.71})
    global_profile = SimpleNamespace(id=uuid.uuid4(), profile={"min_edge_accept_score": 0.63})
    session = MagicMock()
    session.query.side_effect = [
        _query_first(collection_profile),
    ]

    profile_id, profile = build_context._load_threshold_profile(session, "col-1", "default")

    assert profile_id == str(collection_profile.id)
    assert profile["min_edge_accept_score"] == 0.71

    session = MagicMock()
    session.query.side_effect = [
        _query_first(None),
        _query_first(global_profile),
    ]
    monkeypatch.setattr(build_context, "config", SimpleNamespace(threshold_profile_global_fallback=True))

    fallback_id, fallback_profile = build_context._load_threshold_profile(session, "col-1", "default")

    assert fallback_id == str(global_profile.id)
    assert fallback_profile["min_edge_accept_score"] == 0.63


def test_build_evidence_index_limits_examples_per_concept():
    concept = SimpleNamespace(id=uuid.uuid4(), canonical="battery storage", lang="en")
    occ1 = SimpleNamespace(concept_id=concept.id, snippet="battery storage supports resilience", confidence=0.8)
    occ2 = SimpleNamespace(concept_id=concept.id, snippet="battery storage balances load", confidence=0.7)
    chunk1 = SimpleNamespace(text="battery storage supports resilience", lang="en", document_id=uuid.uuid4())
    chunk2 = SimpleNamespace(text="battery storage balances load", lang="en", document_id=uuid.uuid4())
    session = MagicMock()
    session.query.return_value = _query_all([(occ1, chunk1), (occ2, chunk2)])

    index = build_context._build_evidence_index(session, [concept], max_per_concept=1)

    assert list(index.keys()) == ["battery storage"]
    assert len(index["battery storage"]) == 1


def test_load_build_context_assembles_all_runtime_inputs(monkeypatch):
    concept = SimpleNamespace(id=uuid.uuid4(), canonical="battery storage", score=0.8, collection_id="col-1")
    document = SimpleNamespace(id=uuid.uuid4())
    chunk = SimpleNamespace(document_id=document.id, lang="en")
    session = MagicMock()
    session.query.side_effect = [
        _query_all([concept]),
        _query_all([document]),
        _query_all([chunk]),
    ]
    fake_settings = SimpleNamespace(
        threshold_profile_name="default",
        edge_ranker_enabled=True,
        edge_ranker_model_path="/tmp/missing.joblib",
        evidence_linking_enabled=True,
        evidence_top_k=2,
        method="hybrid",
    )
    monkeypatch.setattr(build_context, "load_build_settings", lambda params, concept_count: fake_settings)
    monkeypatch.setattr(build_context, "compute_concept_doc_freq", lambda session, concepts: {"battery storage": 3})
    monkeypatch.setattr(build_context, "_load_threshold_profile", lambda session, collection_id, profile_name: ("profile-1", {"min_edge_accept_score": 0.7}))
    monkeypatch.setattr(build_context, "_load_edge_ranker", lambda model_path: {"model": "loaded"})
    monkeypatch.setattr(build_context, "_build_evidence_index", lambda session, concepts, max_per_concept: {"battery storage": [{"snippet": "evidence"}]})

    ctx = build_context.load_build_context(
        session,
        job_id="job-1",
        collection_id="col-1",
        taxonomy_version_id="tax-1",
        params={"method_taxonomy": "hybrid"},
    )

    assert ctx.job_id == "job-1"
    assert ctx.concept_map["battery storage"] == concept
    assert ctx.concept_doc_freq["battery storage"] == 3
    assert ctx.dominant_lang == "en"
    assert ctx.threshold_profile_id == "profile-1"
    assert ctx.ranker == {"model": "loaded"}
    assert ctx.evidence_index["battery storage"][0]["snippet"] == "evidence"
