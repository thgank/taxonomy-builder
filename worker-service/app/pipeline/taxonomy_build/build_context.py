from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.config import config
from app.db import Concept, Document, DocumentChunk
from app.pipeline.taxonomy_build.build_types import BuildContext
from app.pipeline.taxonomy_build.pair_ops import compute_concept_doc_freq
from app.pipeline.taxonomy_build_settings import load_build_settings


def load_build_context(
    session: Session,
    job_id: str,
    collection_id: str,
    taxonomy_version_id: str,
    params: dict,
) -> BuildContext:
    concepts = (
        session.query(Concept)
        .filter(Concept.collection_id == collection_id)
        .all()
    )
    settings = load_build_settings(params, len(concepts))
    concept_map = {c.canonical: c for c in concepts}
    concept_doc_freq = compute_concept_doc_freq(session, concepts)
    concept_scores = {c.canonical: float(c.score or 0.0) for c in concepts}

    docs = (
        session.query(Document)
        .filter(Document.collection_id == collection_id, Document.status == "PARSED")
        .all()
    )
    doc_ids = [str(d.id) for d in docs]
    chunks = (
        session.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(doc_ids))
        .all()
    )

    lang_groups: dict[str, list[DocumentChunk]] = defaultdict(list)
    for chunk in chunks:
        lang = (chunk.lang or config.default_language or "en").lower()[:2]
        lang_groups[lang].append(chunk)

    lang_counts = dict(Counter({k: len(v) for k, v in lang_groups.items()}))
    dominant_lang = max(lang_counts, key=lang_counts.get) if lang_counts else "en"

    return BuildContext(
        session=session,
        job_id=job_id,
        collection_id=collection_id,
        taxonomy_version_id=taxonomy_version_id,
        params=params,
        settings=settings,
        concepts=concepts,
        concept_map=concept_map,
        concept_doc_freq=concept_doc_freq,
        concept_scores=concept_scores,
        chunks=chunks,
        lang_groups=dict(lang_groups),
        lang_counts=lang_counts,
        dominant_lang=dominant_lang,
        concept_labels=[c.canonical for c in concepts],
        method=settings.method,
    )
