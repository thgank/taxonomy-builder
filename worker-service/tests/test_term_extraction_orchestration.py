from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

from app.pipeline import term_extraction


def _query_with_all(result):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = result
    return query


def test_load_chunks_by_lang_groups_chunks_and_detects_dominant_lang():
    doc1 = SimpleNamespace(id=uuid.uuid4())
    doc2 = SimpleNamespace(id=uuid.uuid4())
    chunk1 = SimpleNamespace(document_id=doc1.id, chunk_index=0, lang="en")
    chunk2 = SimpleNamespace(document_id=doc1.id, chunk_index=1, lang="en")
    chunk3 = SimpleNamespace(document_id=doc2.id, chunk_index=0, lang="ru")
    session = MagicMock()
    session.query.side_effect = [
        _query_with_all([doc1, doc2]),
        _query_with_all([chunk1, chunk2, chunk3]),
    ]

    chunks, chunks_by_lang, dominant_lang = term_extraction._load_chunks_by_lang(session, "collection-1")

    assert chunks == [chunk1, chunk2, chunk3]
    assert dominant_lang == "en"
    assert chunks_by_lang["en"] == [chunk1, chunk2]
    assert chunks_by_lang["ru"] == [chunk3]


def test_extract_scores_merges_tfidf_and_textrank_by_best_language(monkeypatch):
    monkeypatch.setattr(term_extraction, "load_spacy", lambda lang: f"nlp-{lang}")

    def fake_tfidf(chunks, model, max_terms, min_freq, min_doc_freq):
        return {"battery storage": 0.7, "grid balancing": 0.5} if model == "nlp-en" else {"battery storage": 0.9}

    def fake_textrank(chunks, model, max_terms):
        return {"grid balancing": 0.8} if model == "nlp-en" else {"жүйе энергия": 0.6}

    monkeypatch.setattr(term_extraction, "tfidf_extract", fake_tfidf)
    monkeypatch.setattr(term_extraction, "textrank_extract", fake_textrank)

    tfidf_scores, textrank_scores, term_lang_scores = term_extraction._extract_scores(
        {"en": [SimpleNamespace()], "kk": [SimpleNamespace()]},
        "both",
        max_terms=10,
        min_freq=1,
        min_doc_freq=1,
    )

    assert tfidf_scores["battery storage"] == 0.9
    assert textrank_scores["grid balancing"] == 0.8
    assert textrank_scores["жүйе энергия"] == 0.6
    assert term_lang_scores["battery storage"] == ("kk", 0.9)


def test_quality_filter_terms_keeps_only_meaningful_high_quality_terms(monkeypatch):
    monkeypatch.setattr(term_extraction, "compute_term_doc_freq", lambda terms, chunks: {term: 2 for term in terms})
    monkeypatch.setattr(term_extraction, "normalize_score_map", lambda scores: scores)
    monkeypatch.setattr(term_extraction, "suppress_subsumed_single_tokens", lambda scores, df: scores)
    monkeypatch.setattr(term_extraction, "load_spacy", lambda lang: None)
    monkeypatch.setattr(
        term_extraction,
        "is_functional_phrase",
        lambda term, lang, nlp: term == "for use",
    )
    monkeypatch.setattr(
        term_extraction,
        "candidate_quality_score",
        lambda term, base_norm_score, doc_freq, total_docs: 0.85 if term == "grid storage" else 0.4,
    )

    filtered, doc_freq = term_extraction._quality_filter_terms(
        {
            "grid storage": 0.9,
            "for use": 0.9,
            "low": 0.8,
        },
        [SimpleNamespace(document_id="d1"), SimpleNamespace(document_id="d2")],
        {"grid storage": ("en", 0.9), "for use": ("en", 0.9), "low": ("en", 0.8)},
        dominant_lang="en",
        min_doc_freq=1,
        min_quality_score=0.5,
    )

    assert filtered == {"grid storage": 0.9}
    assert doc_freq["grid storage"] == 2


def test_handle_terms_returns_early_when_no_chunks(monkeypatch):
    events = []
    updates = []
    monkeypatch.setattr(term_extraction, "_load_chunks_by_lang", lambda session, collection_id: ([], {}, "en"))
    monkeypatch.setattr(term_extraction, "add_job_event", lambda session, job_id, level, message, meta=None: events.append((level, message)))
    monkeypatch.setattr(term_extraction, "update_job_status", lambda session, job_id, status, **kwargs: updates.append((status, kwargs)))

    term_extraction.handle_terms(MagicMock(), {"jobId": "job-1", "collectionId": "col-1", "params": {}})

    assert events[-1] == ("WARN", "No chunks found for term extraction")
    assert updates[-1][0] == "RUNNING"
    assert updates[-1][1]["progress"] == 100


def test_handle_terms_stores_concepts_and_occurrences(monkeypatch):
    added = []
    commits = []
    updates = []
    events = []

    class FakeConcept:
        collection_id = "collection_id"

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeOccurrence:
        concept_id = "concept_id"

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    chunk = SimpleNamespace(id="chunk-1", document_id="doc-1", lang="en")
    existing_concept = SimpleNamespace(id="old-concept")
    session = MagicMock()
    q_existing = MagicMock()
    q_existing.filter.return_value = q_existing
    q_existing.all.return_value = [existing_concept]
    q_occ_delete = MagicMock()
    q_occ_delete.filter.return_value = q_occ_delete
    q_concept_delete = MagicMock()
    q_concept_delete.filter.return_value = q_concept_delete
    session.query.side_effect = [q_existing, q_occ_delete, q_concept_delete]
    session.add.side_effect = added.append
    session.commit.side_effect = lambda: commits.append("commit")

    monkeypatch.setattr(term_extraction, "Concept", FakeConcept)
    monkeypatch.setattr(term_extraction, "ConceptOccurrence", FakeOccurrence)
    monkeypatch.setattr(term_extraction, "_load_chunks_by_lang", lambda session, collection_id: ([chunk], {"en": [chunk]}, "en"))
    monkeypatch.setattr(term_extraction, "_extract_scores", lambda *args, **kwargs: ({"grid storage": 0.7}, {"energy storage": 0.6}, {"grid storage": ("en", 0.7), "energy storage": ("en", 0.6)}))
    monkeypatch.setattr(term_extraction, "merge_scores", lambda a, b: {**a, **b})
    monkeypatch.setattr(term_extraction, "deduplicate_terms", lambda scores: (scores, {term: [term] for term in scores}))
    monkeypatch.setattr(term_extraction, "refine_term_scores", lambda scores, chunks: scores)
    monkeypatch.setattr(term_extraction, "is_noise_term", lambda term, nlp=None: False)
    monkeypatch.setattr(term_extraction, "is_functional_phrase", lambda term, lang, nlp=None: False)
    monkeypatch.setattr(term_extraction, "_quality_filter_terms", lambda scores, chunks, term_lang_scores, dominant_lang, min_doc_freq, min_quality_score: (scores, {"grid storage": 1, "energy storage": 1}))
    monkeypatch.setattr(term_extraction, "find_occurrences", lambda term, chunks, max_per_term=20: [{"chunk_id": "chunk-1", "snippet": f"{term} matters", "start_offset": 0, "end_offset": 12, "confidence": 0.81}])
    monkeypatch.setattr(term_extraction, "is_job_cancelled", lambda session, job_id: False)
    monkeypatch.setattr(term_extraction, "load_spacy", lambda lang: None)
    monkeypatch.setattr(term_extraction, "add_job_event", lambda session, job_id, level, message, meta=None: events.append((level, message)))
    monkeypatch.setattr(term_extraction, "update_job_status", lambda session, job_id, status, **kwargs: updates.append((status, kwargs)))

    term_extraction.handle_terms(
        session,
        {
            "jobId": "job-1",
            "collectionId": "col-1",
            "params": {"max_terms": 10, "method_term_extraction": "both"},
        },
    )

    concept_rows = [row for row in added if isinstance(row, FakeConcept)]
    occurrence_rows = [row for row in added if isinstance(row, FakeOccurrence)]

    assert len(concept_rows) == 2
    assert len(occurrence_rows) == 2
    assert commits
    assert events[-1] == ("INFO", "Term extraction complete: 2 concepts stored")
    assert updates[-1][1]["progress"] == 100
