"""
Term Extraction worker
──────────────────────
Two methods:
  1. TF-IDF on noun phrases / n-grams
  2. TextRank (graph-based keyword extraction)

Results: concepts + concept_occurrences stored in DB.
"""
from __future__ import annotations

import re
import uuid
import math
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.config import config
from app.db import Document, DocumentChunk, Concept, ConceptOccurrence
from app.job_helper import (
    update_job_status, add_job_event, is_job_cancelled,
)
from app.logger import get_logger

log = get_logger(__name__)

# ── spaCy lazy load ──────────────────────────────────────

_nlp_models: dict[str, Any] = {}


def _load_spacy(lang: str) -> Any:
    if lang not in _nlp_models:
        import spacy
        name = {"en": config.spacy_model_en, "ru": config.spacy_model_ru}.get(lang)
        if name:
            try:
                _nlp_models[lang] = spacy.load(name)
            except OSError:
                _nlp_models[lang] = None
        else:
            _nlp_models[lang] = None
    return _nlp_models.get(lang)


# ── Stopwords (minimal) ─────────────────────────────────

STOP_EN = set("the a an is are was were be been being have has had do does did will would shall "
              "should may might can could of in to for on with at by from as into about between "
              "through during before after above below and or but not no nor so if then that this "
              "these those it its he she they we you i my your his her our their me him us them".split())

STOP_RU = set("и в не на с что как по это он она они мы вы я а но за то все его её их этот эта "
              "эти из к у так уже от при бы до который когда только или тоже ещё более".split())

STOPWORDS = STOP_EN | STOP_RU


# ── Normalization ────────────────────────────────────────

def normalize_term(term: str, nlp_model: Any = None) -> str | None:
    """Normalize: lowercase → lemmatize → filter junk."""
    term = term.strip().lower()
    # remove tokens < 2 chars total
    if len(term) < 2:
        return None
    # remove purely numeric
    if re.match(r"^\d+$", term):
        return None
    # stopword single-token filter
    tokens = term.split()
    if len(tokens) == 1 and tokens[0] in STOPWORDS:
        return None
    # lemmatize with spaCy if available
    if nlp_model:
        doc = nlp_model(term)
        lemmas = [t.lemma_ for t in doc if not t.is_punct and not t.is_space]
        if lemmas:
            term = " ".join(lemmas).strip().lower()
    if not term or len(term) < 2:
        return None
    return term


# ── Method 1: TF-IDF on n-grams ─────────────────────────

def extract_noun_phrases_spacy(text: str, nlp_model: Any) -> list[str]:
    """Extract noun phrases using spaCy."""
    doc = nlp_model(text[:100_000])  # limit to avoid OOM
    phrases = []
    for np in doc.noun_chunks:
        clean = np.text.strip()
        if 2 <= len(clean.split()) <= 4:
            phrases.append(clean)
    # also single nouns
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and len(token.text) > 2:
            phrases.append(token.text)
    return phrases


def extract_ngrams(text: str, ns: tuple[int, ...] = (1, 2, 3)) -> list[str]:
    """Fallback: extract n-grams from tokens."""
    tokens = re.findall(r"\b\w{2,}\b", text.lower())
    tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
    grams = []
    for n in ns:
        for i in range(len(tokens) - n + 1):
            grams.append(" ".join(tokens[i : i + n]))
    return grams


def tfidf_extract(
    chunks: list[DocumentChunk],
    nlp_model: Any,
    max_terms: int,
    min_freq: int,
) -> dict[str, float]:
    """
    TF-IDF scoring of candidate terms across chunks.
    Returns {normalized_term: score}.
    """
    # term → doc_ids (for IDF)
    term_doc_map: dict[str, set] = defaultdict(set)
    # term → total count (for TF)
    term_count: Counter = Counter()

    for chunk in chunks:
        if nlp_model:
            candidates = extract_noun_phrases_spacy(chunk.text, nlp_model)
        else:
            candidates = extract_ngrams(chunk.text)

        seen_in_chunk: set[str] = set()
        for raw in candidates:
            norm = normalize_term(raw, nlp_model)
            if not norm:
                continue
            term_count[norm] += 1
            if norm not in seen_in_chunk:
                term_doc_map[norm].add(str(chunk.id))
                seen_in_chunk.add(norm)

    # Filter by min frequency
    num_docs = len(set(str(c.document_id) for c in chunks))
    if num_docs == 0:
        num_docs = 1

    scores: dict[str, float] = {}
    for term, count in term_count.items():
        if count < min_freq:
            continue
        tf = math.log1p(count)
        idf = math.log1p(num_docs / len(term_doc_map[term]))
        scores[term] = round(tf * idf, 4)

    # Sort and limit
    sorted_terms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_terms[:max_terms])


# ── Method 2: TextRank ───────────────────────────────────

def textrank_extract(
    chunks: list[DocumentChunk],
    nlp_model: Any,
    max_terms: int,
    window: int = 4,
    iterations: int = 30,
    damping: float = 0.85,
) -> dict[str, float]:
    """
    Simple TextRank for keyword extraction.
    Builds co-occurrence graph over candidate tokens, runs PageRank.
    """
    import numpy as np

    # Collect all candidate tokens
    all_tokens: list[list[str]] = []
    for chunk in chunks:
        text = chunk.text.lower()
        tokens = re.findall(r"\b\w{2,}\b", text)
        tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
        if nlp_model:
            doc = nlp_model(chunk.text[:50_000])
            tokens = [
                t.lemma_.lower()
                for t in doc
                if t.pos_ in ("NOUN", "PROPN", "ADJ") and len(t.text) > 2
            ]
        all_tokens.append(tokens)

    # Build vocabulary
    vocab: dict[str, int] = {}
    for tokens in all_tokens:
        for t in tokens:
            if t not in vocab:
                vocab[t] = len(vocab)

    n = len(vocab)
    if n == 0:
        return {}

    # Build co-occurrence matrix
    cooccur = np.zeros((n, n), dtype=np.float32)
    for tokens in all_tokens:
        for i, t1 in enumerate(tokens):
            for j in range(i + 1, min(i + window + 1, len(tokens))):
                t2 = tokens[j]
                if t1 in vocab and t2 in vocab:
                    idx1, idx2 = vocab[t1], vocab[t2]
                    cooccur[idx1][idx2] += 1
                    cooccur[idx2][idx1] += 1

    # Normalize columns
    col_sums = cooccur.sum(axis=0)
    col_sums[col_sums == 0] = 1
    matrix = cooccur / col_sums

    # PageRank iteration
    scores = np.ones(n) / n
    for _ in range(iterations):
        scores = (1 - damping) / n + damping * matrix @ scores

    # Map back
    inv_vocab = {v: k for k, v in vocab.items()}
    result: dict[str, float] = {}
    for idx in range(n):
        term = inv_vocab[idx]
        result[term] = round(float(scores[idx]), 6)

    sorted_terms = sorted(result.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_terms[:max_terms])


# ── Merge results from both methods ──────────────────────

def merge_scores(
    tfidf_scores: dict[str, float],
    textrank_scores: dict[str, float],
    alpha: float = 0.6,  # weight for TF-IDF
) -> dict[str, float]:
    """Combine TF-IDF and TextRank scores with normalization."""
    all_terms = set(tfidf_scores) | set(textrank_scores)
    if not all_terms:
        return {}

    # Normalize to [0, 1]
    def norm(d: dict[str, float]) -> dict[str, float]:
        if not d:
            return {}
        mx = max(d.values()) or 1.0
        return {k: v / mx for k, v in d.items()}

    n_tfidf = norm(tfidf_scores)
    n_tr = norm(textrank_scores)

    merged: dict[str, float] = {}
    for term in all_terms:
        s = alpha * n_tfidf.get(term, 0) + (1 - alpha) * n_tr.get(term, 0)
        merged[term] = round(s, 4)

    return dict(sorted(merged.items(), key=lambda x: x[1], reverse=True))


# ── Deduplication with fuzzy matching ────────────────────

def deduplicate_terms(
    terms: dict[str, float],
    threshold: int | None = None,
) -> dict[str, float]:
    """Merge near-duplicate terms using rapidfuzz."""
    if threshold is None:
        threshold = config.fuzz_threshold

    from rapidfuzz import fuzz

    canonical_map: dict[str, str] = {}  # surface → canonical
    canonical_scores: dict[str, float] = {}
    surface_lists: dict[str, list[str]] = {}

    sorted_terms = sorted(terms.items(), key=lambda x: x[1], reverse=True)

    for term, score in sorted_terms:
        matched = False
        for canon in list(canonical_scores.keys()):
            if fuzz.ratio(term, canon) >= threshold:
                # Merge into existing canonical (keep higher-scored one)
                surface_lists[canon].append(term)
                if score > canonical_scores[canon]:
                    canonical_scores[canon] = score
                matched = True
                break
        if not matched:
            canonical_scores[term] = score
            surface_lists[term] = [term]

    return canonical_scores, surface_lists


# ── Occurrence extraction ────────────────────────────────

def find_occurrences(
    term: str,
    chunks: list[DocumentChunk],
    max_per_term: int = 20,
) -> list[dict]:
    """Find snippets where term appears in chunks."""
    occurrences = []
    pattern = re.compile(re.escape(term), re.IGNORECASE)

    for chunk in chunks:
        for match in pattern.finditer(chunk.text):
            start = max(0, match.start() - 50)
            end = min(len(chunk.text), match.end() + 50)
            snippet = chunk.text[start:end]
            occurrences.append({
                "chunk_id": str(chunk.id),
                "snippet": snippet,
                "start_offset": match.start(),
                "end_offset": match.end(),
                "confidence": 0.8,
            })
            if len(occurrences) >= max_per_term:
                return occurrences
    return occurrences


# ── Handler ──────────────────────────────────────────────

def handle_terms(session: Session, msg: dict) -> None:
    """Term extraction handler."""
    job_id = str(msg.get("jobId") or msg.get("job_id"))
    collection_id = str(msg.get("collectionId") or msg.get("collection_id"))
    params = msg.get("params", {})

    update_job_status(session, job_id, "RUNNING", progress=0)
    add_job_event(session, job_id, "INFO", "Term extraction started")

    max_terms = int(params.get("max_terms", config.max_terms))
    min_freq = int(params.get("min_freq", config.min_term_freq))
    method = params.get("method_term_extraction", "both")

    # Get all chunks for collection
    docs = (
        session.query(Document)
        .filter(Document.collection_id == collection_id, Document.status == "PARSED")
        .all()
    )
    doc_ids = [str(d.id) for d in docs]
    chunks = (
        session.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(doc_ids))
        .order_by(DocumentChunk.chunk_index)
        .all()
    )

    if not chunks:
        add_job_event(session, job_id, "WARN", "No chunks found for term extraction")
        update_job_status(session, job_id, "RUNNING", progress=100)
        return

    # Detect dominant language
    langs = Counter(c.lang for c in chunks if c.lang)
    dominant_lang = langs.most_common(1)[0][0] if langs else "en"
    nlp_model = _load_spacy(dominant_lang)

    add_job_event(session, job_id, "INFO", f"Dominant language: {dominant_lang}")
    update_job_status(session, job_id, "RUNNING", progress=10)

    # Extract terms
    tfidf_scores: dict[str, float] = {}
    textrank_scores: dict[str, float] = {}

    if method in ("tfidf", "both"):
        tfidf_scores = tfidf_extract(chunks, nlp_model, max_terms * 2, min_freq)
        add_job_event(session, job_id, "INFO",
                      f"TF-IDF extracted {len(tfidf_scores)} candidates")

    update_job_status(session, job_id, "RUNNING", progress=30)

    if method in ("textrank", "both"):
        textrank_scores = textrank_extract(chunks, nlp_model, max_terms * 2)
        add_job_event(session, job_id, "INFO",
                      f"TextRank extracted {len(textrank_scores)} candidates")

    update_job_status(session, job_id, "RUNNING", progress=50)

    # Merge
    if method == "both":
        final_scores = merge_scores(tfidf_scores, textrank_scores)
    elif method == "tfidf":
        final_scores = tfidf_scores
    else:
        final_scores = textrank_scores

    # Deduplicate
    deduped_scores, surface_map = deduplicate_terms(final_scores)

    # Limit
    top_terms = dict(list(deduped_scores.items())[:max_terms])

    add_job_event(session, job_id, "INFO",
                  f"After dedup: {len(top_terms)} terms")
    update_job_status(session, job_id, "RUNNING", progress=60)

    # Delete existing concepts for idempotency
    existing = session.query(Concept).filter(
        Concept.collection_id == collection_id
    ).all()
    for c in existing:
        session.query(ConceptOccurrence).filter(
            ConceptOccurrence.concept_id == c.id
        ).delete()
    session.query(Concept).filter(
        Concept.collection_id == collection_id
    ).delete()
    session.commit()

    # Store concepts + occurrences
    stored = 0
    for term, score in top_terms.items():
        if is_job_cancelled(session, job_id):
            return

        concept = Concept(
            id=uuid.uuid4(),
            collection_id=collection_id,
            canonical=term,
            surface_forms=surface_map.get(term, [term]),
            lang=dominant_lang,
            score=score,
        )
        session.add(concept)
        session.flush()

        # Find occurrences
        occs = find_occurrences(term, chunks)
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

    add_job_event(session, job_id, "INFO",
                  f"Term extraction complete: {stored} concepts stored")
    update_job_status(session, job_id, "RUNNING", progress=100)
    log.info("Term extraction complete for collection %s: %d concepts", collection_id, stored)
