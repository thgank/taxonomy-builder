"""
NLP preprocessing worker
─────────────────────────
Language detection + tokenization/lemmatization for chunks.
Stores detected language on each chunk row.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config import config
from app.db import Document, DocumentChunk
from app.job_helper import (
    update_job_status, add_job_event, is_job_cancelled,
)
from app.logger import get_logger

log = get_logger(__name__)

# Lazy-loaded spaCy models
_models: dict[str, Any] = {}


def _get_spacy_model(lang: str) -> Any:
    """Load spaCy model on first use."""
    if lang not in _models:
        import spacy
        model_name = {
            "en": config.spacy_model_en,
            "ru": config.spacy_model_ru,
        }.get(lang)
        if model_name:
            try:
                _models[lang] = spacy.load(model_name)
                log.info("Loaded spaCy model %s", model_name)
            except OSError:
                log.warning("spaCy model %s not found, skipping NLP for %s", model_name, lang)
                _models[lang] = None
        else:
            _models[lang] = None
    return _models.get(lang)


def detect_language(text: str) -> str:
    """Detect language of a text snippet."""
    try:
        from langdetect import detect
        return detect(text[:2000])
    except Exception:
        return "en"


def handle_nlp(session: Session, msg: dict) -> None:
    """Process NLP message: detect lang, annotate chunks."""
    job_id = str(msg.get("jobId") or msg.get("job_id"))
    collection_id = str(msg.get("collectionId") or msg.get("collection_id"))
    params = msg.get("params", {})

    update_job_status(session, job_id, "RUNNING", progress=0)
    add_job_event(session, job_id, "INFO", "NLP preprocessing started")

    # Get all PARSED documents in the collection
    docs = (
        session.query(Document)
        .filter(
            Document.collection_id == collection_id,
            Document.status == "PARSED",
        )
        .all()
    )

    all_chunks = []
    for doc in docs:
        chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        add_job_event(session, job_id, "WARN", "No chunks to process")
        update_job_status(session, job_id, "RUNNING", progress=100)
        return

    total = len(all_chunks)
    lang_counts: dict[str, int] = {}

    for idx, chunk in enumerate(all_chunks):
        if idx % 200 == 0 and is_job_cancelled(session, job_id):
            return

        # Detect language if not set
        if not chunk.lang:
            lang = detect_language(chunk.text)
            chunk.lang = lang[:10]

        lang_counts[chunk.lang] = lang_counts.get(chunk.lang, 0) + 1

        if (idx + 1) % 100 == 0:
            session.commit()
            progress = int(((idx + 1) / total) * 100)
            update_job_status(session, job_id, "RUNNING", progress=progress)

    session.commit()

    add_job_event(
        session, job_id, "INFO",
        f"NLP finished: {total} chunks, langs: {lang_counts}",
    )
    update_job_status(session, job_id, "RUNNING", progress=100)
    log.info("NLP complete for collection %s", collection_id)
