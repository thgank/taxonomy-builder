from types import SimpleNamespace
import uuid

from app.pipeline.taxonomy_build import build_generation


def _concept(label, lang="en"):
    return SimpleNamespace(id=uuid.uuid4(), canonical=label, lang=lang, score=0.8)


def _ctx(method="hybrid", **settings_overrides):
    concepts = [
        _concept("energy", "en"),
        _concept("battery storage", "en"),
        _concept("grid battery storage", "en"),
    ]
    concept_map = {c.canonical: c for c in concepts}
    settings = SimpleNamespace(
        hearst_soft_mode=True,
        hearst_trigger_fallback_enabled=True,
        hearst_trigger_fallback_max_pairs=8,
        sim_threshold=0.55,
        parent_pool_size=2,
        max_children_per_parent=2,
        adaptive_percentile=50,
        min_parent_doc_freq=1,
        adaptive_edge_accept_percentile=50,
        adaptive_thresholds_enabled=False,
        evidence_linking_enabled=True,
        edge_ranker_enabled=False,
        edge_ranker_min_confidence=0.7,
        edge_ranker_blend_alpha=0.5,
        global_selector_enabled=True,
        max_depth=4,
    )
    for key, value in settings_overrides.items():
        setattr(settings, key, value)
    return SimpleNamespace(
        session=SimpleNamespace(),
        job_id="job-1",
        collection_id="col-1",
        taxonomy_version_id="tax-1",
        params={},
        settings=settings,
        concepts=concepts,
        concept_map=concept_map,
        concept_doc_freq={"energy": 7, "battery storage": 5, "grid battery storage": 3},
        concept_scores={c.canonical: c.score for c in concepts},
        chunks=[SimpleNamespace(text="energy such as battery storage", lang="en", document_id="doc-1")],
        lang_groups={"en": [SimpleNamespace(text="energy such as battery storage", lang="en", document_id="doc-1")]},
        lang_counts={"en": 1},
        dominant_lang="en",
        concept_labels=list(concept_map.keys()),
        method=method,
        threshold_profile_id="profile-1",
        threshold_profile={"hearst": 0.6},
        ranker=None,
        evidence_index={},
    )


def test_merge_duplicate_pairs_combines_score_and_evidence():
    pairs = [
        {"hypernym": "energy", "hyponym": "battery storage", "score": 0.6, "evidence": {"source": "hearst"}},
        {"hypernym": "energy", "hyponym": "battery storage", "score": 0.8, "evidence": [{"source": "embed"}]},
        {"hypernym": "energy", "hyponym": "grid battery storage", "score": 0.5, "evidence": []},
    ]

    merged = build_generation._merge_duplicate_pairs(pairs)

    assert len(merged) == 2
    first = merged[0]
    assert first["score"] == 0.8
    assert len(first["evidence"]) == 2


def test_extract_edge_features_candidate_log_and_risk_are_populated():
    ctx = _ctx()
    edge = {
        "hypernym": "energy",
        "hyponym": "battery storage",
        "score": 0.74,
        "evidence": [
            {"semantic_similarity": 0.81, "lexical_similarity": 0.25},
            {"cosine_similarity": 0.77},
        ],
    }

    features = build_generation.extract_edge_features(
        ctx,
        edge,
        cooc_support={("energy", "battery storage"): 0.45},
        parent_degree={"energy": 2},
    )
    log = build_generation.build_candidate_log(
        ctx,
        edge,
        features,
        decision="accepted",
        rejection_reason=None,
        min_score=0.55,
        ranker_score=0.8,
        evidence_score=0.7,
    )

    assert features["lang"] == "en"
    assert features["semantic_similarity"] == 0.81
    assert features["cooccurrence_support"] == 0.45
    assert log["parent_label"] == "energy"
    assert log["parent_concept_id"] == str(ctx.concept_map["energy"].id)
    assert 0.0 <= log["risk_score"] <= 1.0


def test_predict_ranker_score_handles_probability_predictions_and_failures():
    class ProbaModel:
        feature_names_in_ = ["base_score", "semantic_similarity"]

        def predict_proba(self, vector):
            assert vector == [[0.7, 0.9]]
            return [[0.15, 0.85]]

    class BrokenModel:
        def predict(self, _vector):
            raise RuntimeError("boom")

    ctx = _ctx()
    ctx.settings.edge_ranker_enabled = True
    ctx.ranker = {"model": ProbaModel()}

    score = build_generation.predict_ranker_score(
        ctx,
        {"base_score": 0.7, "semantic_similarity": 0.9, "method": "hearst"},
    )

    assert score == 0.85
    ctx.ranker = BrokenModel()
    assert build_generation.predict_ranker_score(ctx, {"base_score": 0.1}) is None


def test_build_all_relation_candidates_combines_hearst_trigger_and_embedding(monkeypatch):
    ctx = _ctx()
    events = []
    progresses = []

    monkeypatch.setattr(
        build_generation,
        "extract_hearst_pairs",
        lambda _chunks, _concepts, _lang, soft_mode=False: (
            [{"hypernym": "energy", "hyponym": "battery storage", "score": 0.7, "evidence": {"method": "hearst_soft"}}]
            if soft_mode
            else [{"hypernym": "energy", "hyponym": "battery storage", "score": 0.8, "evidence": {"method": "hearst"}}]
        ),
    )
    monkeypatch.setattr(
        build_generation,
        "extract_hearst_trigger_pairs",
        lambda *_args, **_kwargs: [
            {"hypernym": "energy", "hyponym": "grid battery storage", "score": 0.65, "evidence": {"method": "hearst_trigger_fallback"}}
        ],
    )
    monkeypatch.setattr(
        build_generation,
        "build_embedding_hierarchy",
        lambda *_args, **_kwargs: [
            {"hypernym": "energy", "hyponym": "battery storage", "score": 0.76, "evidence": {"method": "embedding_clustering"}}
        ],
    )
    monkeypatch.setattr(build_generation, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(build_generation, "update_job_status", lambda _session, _job_id, _status, progress=0: progresses.append(progress))

    pairs = build_generation.build_all_relation_candidates(ctx)

    assert len(pairs) == 4
    assert progresses == [30, 60]
    assert any("Hearst patterns found 3 relations" in message for _level, message in events)
    assert any("Embedding clustering found 1 relations" in message for _level, message in events)


def test_build_initial_state_accepts_rejects_and_defers_soft_failures(monkeypatch):
    ctx = _ctx()
    pairs = [
        {"hypernym": "energy", "hyponym": "battery storage", "score": 0.82, "evidence": {"method": "hearst"}},
        {"hypernym": "energy", "hyponym": "grid battery storage", "score": 0.41, "evidence": {"method": "hearst"}},
        {"hypernym": "energy", "hyponym": "voltage", "score": 0.49, "evidence": {"method": "embedding_clustering"}},
    ]
    candidate_logs = []

    monkeypatch.setattr(build_generation, "collapse_bidirectional_pairs", lambda current, _freq: current)
    monkeypatch.setattr(build_generation, "remove_cycles", lambda current: current)
    monkeypatch.setattr(build_generation, "limit_depth", lambda current, _depth: current)
    monkeypatch.setattr(build_generation, "adaptive_method_thresholds", lambda _pairs, _score, _pct: {"hearst": 0.5, "embedding_clustering": 0.5})
    monkeypatch.setattr(build_generation, "compute_pair_cooccurrence", lambda _chunks, _labels: {("energy", "battery storage"): 0.3})
    monkeypatch.setattr(build_generation, "edge_min_score", lambda edge, _default, _thresholds: 0.5 if edge["hyponym"] != "voltage" else 0.55)
    monkeypatch.setattr(build_generation, "blend_scores", lambda **kwargs: kwargs["base_score"] + (0.05 if kwargs.get("evidence_score") else 0.0))
    monkeypatch.setattr(build_generation, "method_weight", lambda _method: 0.7)
    monkeypatch.setattr(build_generation, "predict_ranker_score", lambda _ctx, _features: None)
    monkeypatch.setattr(build_generation, "add_job_event", lambda *_args, **_kwargs: None)

    def fake_reason(edge, _freq, min_score):
        if edge["hyponym"] == "battery storage":
            return None
        if edge["hyponym"] == "grid battery storage":
            return "score_below_threshold"
        assert min_score == 0.55
        return "single_to_single"

    monkeypatch.setattr(build_generation, "edge_rejection_reason", fake_reason)
    original_log_builder = build_generation.build_candidate_log
    monkeypatch.setattr(
        build_generation,
        "build_candidate_log",
        lambda *args, **kwargs: candidate_logs.append(original_log_builder(*args, **kwargs)) or candidate_logs[-1],
    )

    state = build_generation.build_initial_state(ctx, pairs)

    assert len(state.unique_pairs) == 1
    assert state.unique_pairs[0]["hyponym"] == "battery storage"
    assert len(state.connectivity_candidate_pool) == 2
    assert len(state.candidate_logs) == 3
    assert candidate_logs[0]["decision"] == "accepted"
    assert candidate_logs[1]["decision"] == "rejected"

