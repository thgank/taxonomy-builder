"""
Term Extraction worker orchestration.

Algorithmic details live in dedicated modules:
- term_extraction_cleaning
- term_extraction_methods
- term_extraction_scoring
- term_extraction_occurrence
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.config import config
from app.db import Concept, ConceptOccurrence, Document, DocumentChunk
from app.job_helper import add_job_event, is_job_cancelled, update_job_status
from app.logger import get_logger
from app.pipeline.term_extraction_cleaning import (
    is_functional_phrase,
    is_noise_term,
    is_noise_token,
)
from app.pipeline.term_extraction_constants import BAD_SINGLE_TOKENS, TOKEN_RE
from app.pipeline.term_extraction_methods import merge_scores, textrank_extract, tfidf_extract
from app.pipeline.term_extraction_occurrence import find_occurrences
from app.pipeline.term_extraction_scoring import (
    candidate_quality_score,
    compute_term_doc_freq,
    deduplicate_terms,
    normalize_score_map,
    refine_term_scores,
    suppress_subsumed_single_tokens,
)
from app.pipeline.term_extraction_spacy import load_spacy

log = get_logger(__name__)


def _load_chunks_by_lang(session: Session, collection_id: str) -> tuple[list[DocumentChunk], dict[str, list[DocumentChunk]], str]:
    docs = (
        session.query(Document)
        .filter(Document.collection_id == collection_id, Document.status == "PARSED")
        .all()
    )
    doc_ids = [str(d.id) for d in docs]
    chunks = (
        session.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(doc_ids))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        .all()
    )
    chunks_by_lang: dict[str, list[DocumentChunk]] = defaultdict(list)
    for c in chunks:
        lang = (c.lang or config.default_language or "en").lower()[:2]
        chunks_by_lang[lang].append(c)
    dominant_lang = Counter({k: len(v) for k, v in chunks_by_lang.items()}).most_common(1)[0][0] if chunks_by_lang else "en"
    return chunks, chunks_by_lang, dominant_lang


def _extract_scores(
    chunks_by_lang: dict[str, list[DocumentChunk]],
    method: str,
    max_terms: int,
    min_freq: int,
    min_doc_freq: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, tuple[str, float]]]:
    tfidf_scores: dict[str, float] = {}
    textrank_scores: dict[str, float] = {}
    term_lang_scores: dict[str, tuple[str, float]] = {}
    for lang, lang_chunks in chunks_by_lang.items():
        nlp_model = load_spacy(lang)
        if method in ("tfidf", "both"):
            lang_scores = tfidf_extract(lang_chunks, nlp_model, max_terms * 2, min_freq, min_doc_freq)
            for term, score in lang_scores.items():
                if score > tfidf_scores.get(term, 0.0):
                    tfidf_scores[term] = score
                prev = term_lang_scores.get(term)
                if prev is None or score > prev[1]:
                    term_lang_scores[term] = (lang, float(score))
        if method in ("textrank", "both"):
            lang_scores = textrank_extract(lang_chunks, nlp_model, max_terms * 2)
            for term, score in lang_scores.items():
                if score > textrank_scores.get(term, 0.0):
                    textrank_scores[term] = score
                prev = term_lang_scores.get(term)
                if prev is None or score > prev[1]:
                    term_lang_scores[term] = (lang, float(score))
    return tfidf_scores, textrank_scores, term_lang_scores


def _quality_filter_terms(
    deduped_scores: dict[str, float],
    chunks: list[DocumentChunk],
    term_lang_scores: dict[str, tuple[str, float]],
    dominant_lang: str,
    min_doc_freq: int,
    min_quality_score: float,
) -> tuple[dict[str, float], dict[str, int]]:
    total_docs = max(1, len({str(c.document_id) for c in chunks}))
    term_doc_freq = compute_term_doc_freq(list(deduped_scores.keys()), chunks)
    norm_refined = normalize_score_map(deduped_scores)
    deduped_scores = suppress_subsumed_single_tokens(deduped_scores, term_doc_freq)

    quality_filtered: dict[str, float] = {}
    single_token_extra = 0.17
    for term, score in deduped_scores.items():
        df = int(term_doc_freq.get(term, 0))
        if df < min_doc_freq:
            continue
        toks = [t.lower() for t in TOKEN_RE.findall(term)]
        if not toks:
            continue
        if len(toks) == 1:
            if len(toks[0]) < 4:
                continue
            if toks[0] in BAD_SINGLE_TOKENS or is_noise_token(toks[0]):
                continue
        term_lang = term_lang_scores.get(term, (dominant_lang, 0.0))[0]
        if is_functional_phrase(term, term_lang, load_spacy(term_lang)):
            continue
        q_score = candidate_quality_score(
            term,
            base_norm_score=float(norm_refined.get(term, 0.0)),
            doc_freq=df,
            total_docs=total_docs,
        )
        dynamic_threshold = min_quality_score + (single_token_extra if len(toks) == 1 else 0.0)
        if q_score < dynamic_threshold:
            continue
        quality_filtered[term] = score
    return quality_filtered, term_doc_freq


def handle_terms(session: Session, msg: dict) -> None:
    job_id = str(msg.get("jobId") or msg.get("job_id"))
    collection_id = str(msg.get("collectionId") or msg.get("collection_id"))
    params = msg.get("params", {})

    update_job_status(session, job_id, "RUNNING", progress=0)
    add_job_event(session, job_id, "INFO", "Term extraction started")

    max_terms = int(params.get("max_terms", config.max_terms))
    min_freq = int(params.get("min_freq", config.min_term_freq))
    min_doc_freq = int(params.get("min_doc_freq", config.min_doc_freq))
    min_quality_score = float(params.get("min_term_quality_score", config.min_term_quality_score))
    method = params.get("method_term_extraction", "both")

    chunks, chunks_by_lang, dominant_lang = _load_chunks_by_lang(session, collection_id)
    if not chunks:
        add_job_event(session, job_id, "WARN", "No chunks found for term extraction")
        update_job_status(session, job_id, "RUNNING", progress=100)
        return

    add_job_event(
        session,
        job_id,
        "INFO",
        f"Chunk language split: { {k: len(v) for k, v in chunks_by_lang.items()} }",
    )
    update_job_status(session, job_id, "RUNNING", progress=10)

    tfidf_scores, textrank_scores, term_lang_scores = _extract_scores(
        chunks_by_lang,
        method,
        max_terms,
        min_freq,
        min_doc_freq,
    )
    if method in ("tfidf", "both"):
        add_job_event(session, job_id, "INFO", f"TF-IDF extracted {len(tfidf_scores)} candidates")
    update_job_status(session, job_id, "RUNNING", progress=30)
    if method in ("textrank", "both"):
        add_job_event(session, job_id, "INFO", f"TextRank extracted {len(textrank_scores)} candidates")
    update_job_status(session, job_id, "RUNNING", progress=50)

    if method == "both":
        final_scores = merge_scores(tfidf_scores, textrank_scores)
    elif method == "tfidf":
        final_scores = tfidf_scores
    else:
        final_scores = textrank_scores

    deduped_scores, surface_map = deduplicate_terms(final_scores)
    deduped_scores = refine_term_scores(deduped_scores, chunks)
    deduped_scores = {
        term: score
        for term, score in deduped_scores.items()
        if not is_noise_term(term, load_spacy(term_lang_scores.get(term, (dominant_lang, 0.0))[0]))
        and not is_functional_phrase(
            term,
            term_lang_scores.get(term, (dominant_lang, 0.0))[0],
            load_spacy(term_lang_scores.get(term, (dominant_lang, 0.0))[0]),
        )
    }
    deduped_scores, _term_doc_freq = _quality_filter_terms(
        deduped_scores,
        chunks,
        term_lang_scores,
        dominant_lang,
        min_doc_freq,
        min_quality_score,
    )
    surface_map = {term: forms for term, forms in surface_map.items() if term in deduped_scores}
    term_lang_map = {term: term_lang_scores.get(term, (dominant_lang, 0.0))[0] for term in deduped_scores}
    top_terms = dict(list(deduped_scores.items())[:max_terms])

    add_job_event(
        session,
        job_id,
        "INFO",
        f"After dedup: {len(top_terms)} terms (min_doc_freq={min_doc_freq}, min_quality_score={min_quality_score:.2f})",
    )
    update_job_status(session, job_id, "RUNNING", progress=60)

    existing = session.query(Concept).filter(Concept.collection_id == collection_id).all()
    for c in existing:
        session.query(ConceptOccurrence).filter(ConceptOccurrence.concept_id == c.id).delete()
    session.query(Concept).filter(Concept.collection_id == collection_id).delete()
    session.commit()

    stored = 0
    for term, score in top_terms.items():
        if is_job_cancelled(session, job_id):
            return

        concept = Concept(
            id=uuid.uuid4(),
            collection_id=collection_id,
            canonical=term,
            surface_forms=surface_map.get(term, [term]),
            lang=term_lang_map.get(term, dominant_lang),
            score=score,
        )
        session.add(concept)
        session.flush()

        term_lang = concept.lang or dominant_lang
        lang_chunks = chunks_by_lang.get(term_lang[:2], chunks)
        occs = find_occurrences(
            term,
            lang_chunks,
            max_per_term=config.max_occurrences_per_term,
        ) or find_occurrences(
            term,
            chunks,
            max_per_term=config.max_occurrences_per_term,
        )
        for occ in occs:
            occurrence = ConceptOccurrence(
                id=uuid.uuid4(),
                concept_id=concept.id,
                chunk_id=occ["chunk_id"],
                snippet=occ["snippet"],
                start_offset=occ["start_offset"],
                end_offset=occ["end_offset"],
                confidence=occ["confidence"],
            )
            session.add(occurrence)

        stored += 1
        if stored % 50 == 0:
            session.commit()
            progress = 60 + int((stored / len(top_terms)) * 35)
            update_job_status(session, job_id, "RUNNING", progress=progress)

    session.commit()
    add_job_event(session, job_id, "INFO", f"Term extraction complete: {stored} concepts stored")
    update_job_status(session, job_id, "RUNNING", progress=100)
    log.info("Term extraction complete for collection %s: %d concepts", collection_id, stored)
