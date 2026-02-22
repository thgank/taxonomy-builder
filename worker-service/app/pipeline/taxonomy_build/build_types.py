from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import Concept, DocumentChunk
from app.pipeline.taxonomy_build_settings import BuildSettings


@dataclass
class BuildContext:
    session: Session
    job_id: str
    collection_id: str
    taxonomy_version_id: str
    params: dict
    settings: BuildSettings
    concepts: list[Concept]
    concept_map: dict[str, Concept]
    concept_doc_freq: dict[str, int]
    concept_scores: dict[str, float]
    chunks: list[DocumentChunk]
    lang_groups: dict[str, list[DocumentChunk]]
    lang_counts: dict[str, int]
    dominant_lang: str
    concept_labels: list[str]
    method: str
    threshold_profile_id: str | None
    threshold_profile: dict
    ranker: object | None
    evidence_index: dict[str, list[dict]]


@dataclass
class BuildState:
    unique_pairs: list[dict]
    connectivity_candidate_pool: list[dict]
    min_edge_accept_score: float
    method_thresholds: dict[str, float]
    candidate_logs: list[dict]
    ranker_enabled: bool
