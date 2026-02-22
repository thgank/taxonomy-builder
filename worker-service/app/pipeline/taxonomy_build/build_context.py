from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import config
from app.db import (
    Concept,
    ConceptOccurrence,
    Document,
    DocumentChunk,
    TaxonomyThresholdProfile,
)
from app.pipeline.taxonomy_build.build_types import BuildContext
from app.pipeline.taxonomy_build.pair_ops import compute_concept_doc_freq
from app.pipeline.taxonomy_build_settings import load_build_settings


def _load_threshold_profile(session: Session, collection_id: str, profile_name: str) -> tuple[str | None, dict]:
    collection_profile = (
        session.query(TaxonomyThresholdProfile)
        .filter(
            TaxonomyThresholdProfile.collection_id == collection_id,
            TaxonomyThresholdProfile.is_active.is_(True),
            TaxonomyThresholdProfile.name == profile_name,
        )
        .order_by(TaxonomyThresholdProfile.created_at.desc())
        .first()
    )
    if collection_profile:
        return str(collection_profile.id), dict(collection_profile.profile or {})
    if not config.threshold_profile_global_fallback:
        return None, {}
    global_profile = (
        session.query(TaxonomyThresholdProfile)
        .filter(
            TaxonomyThresholdProfile.collection_id.is_(None),
            TaxonomyThresholdProfile.is_active.is_(True),
            TaxonomyThresholdProfile.name == profile_name,
        )
        .order_by(TaxonomyThresholdProfile.created_at.desc())
        .first()
    )
    if not global_profile:
        return None, {}
    return str(global_profile.id), dict(global_profile.profile or {})


def _load_edge_ranker(model_path: str) -> object | None:
    path = Path(model_path)
    if not path.exists():
        return None
    try:
        import joblib
        return joblib.load(path)
    except Exception:
        return None


def _build_evidence_index(
    session: Session,
    concepts: list[Concept],
    max_per_concept: int,
) -> dict[str, list[dict]]:
    if not concepts:
        return {}
    concept_ids = [c.id for c in concepts]
    rows = (
        session.query(ConceptOccurrence, DocumentChunk)
        .join(DocumentChunk, ConceptOccurrence.chunk_id == DocumentChunk.id)
        .filter(ConceptOccurrence.concept_id.in_(concept_ids))
        .all()
    )
    concept_by_id = {str(c.id): c for c in concepts}
    out: dict[str, list[dict]] = defaultdict(list)
    for occ, chunk in rows:
        concept = concept_by_id.get(str(occ.concept_id))
        if not concept:
            continue
        items = out[concept.canonical]
        if len(items) >= max_per_concept:
            continue
        snippet = (occ.snippet or chunk.text or "").strip()
        if not snippet:
            continue
        items.append(
            {
                "snippet": snippet[:600],
                "lang": (chunk.lang or concept.lang or config.default_language or "en").lower()[:2],
                "document_id": str(chunk.document_id),
                "confidence": float(occ.confidence or 0.0),
            }
        )
    return dict(out)


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
    threshold_profile_id, threshold_profile = _load_threshold_profile(
        session,
        collection_id,
        settings.threshold_profile_name,
    )
    ranker = None
    if settings.edge_ranker_enabled:
        ranker = _load_edge_ranker(settings.edge_ranker_model_path)
    evidence_index: dict[str, list[dict]] = {}
    if settings.evidence_linking_enabled:
        evidence_index = _build_evidence_index(
            session,
            concepts,
            max_per_concept=max(1, settings.evidence_top_k),
        )

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
        threshold_profile_id=threshold_profile_id,
        threshold_profile=threshold_profile,
        ranker=ranker,
        evidence_index=evidence_index,
    )
