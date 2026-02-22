"""
SQLAlchemy engine, session, and ORM models matching the Flyway schema.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    ForeignKey, DateTime, BigInteger, Index, create_engine, JSON,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import (
    declarative_base, relationship, sessionmaker, Session,
)

from app.config import config

engine = create_engine(
    config.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── Collections ──────────────────────────────────────────

class Collection(Base):
    __tablename__ = "collections"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    active_job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", use_alter=True))


# ── Documents ────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id"), nullable=False)
    filename = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, default=0)
    storage_path = Column(Text)
    status = Column(String(16), nullable=False, default="NEW")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    parsed_at = Column(DateTime(timezone=True))

    collection = relationship("Collection")


# ── Document Chunks ──────────────────────────────────────

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    lang = Column(String(10))
    char_start = Column(Integer)
    char_end = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    document = relationship("Document")


# ── Concepts ─────────────────────────────────────────────

class Concept(Base):
    __tablename__ = "concepts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id"), nullable=False)
    canonical = Column(Text, nullable=False)
    surface_forms = Column(JSONB, default=list)
    lang = Column(String(10))
    score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    collection = relationship("Collection")


# ── Concept Occurrences ──────────────────────────────────

class ConceptOccurrence(Base):
    __tablename__ = "concept_occurrences"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=False)
    snippet = Column(Text)
    start_offset = Column(Integer)
    end_offset = Column(Integer)
    confidence = Column(Float, nullable=False, default=0.0)

    concept = relationship("Concept")
    chunk = relationship("DocumentChunk")


# ── Taxonomy Versions ────────────────────────────────────

class TaxonomyVersion(Base):
    __tablename__ = "taxonomy_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id"), nullable=False)
    algorithm = Column(String(64), nullable=False, default="hybrid")
    parameters = Column(JSONB, default=dict)
    status = Column(String(16), nullable=False, default="NEW")
    quality_metrics = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    finished_at = Column(DateTime(timezone=True))

    collection = relationship("Collection")


# ── Taxonomy Edges ───────────────────────────────────────

class TaxonomyEdge(Base):
    __tablename__ = "taxonomy_edges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    taxonomy_version_id = Column(UUID(as_uuid=True), ForeignKey("taxonomy_versions.id"), nullable=False)
    parent_concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    child_concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    relation = Column(String(32), nullable=False, default="is_a")
    score = Column(Float, nullable=False, default=0.0)
    evidence = Column(JSONB, default=list)
    approved = Column("approved", type_=Boolean)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    taxonomy_version = relationship("TaxonomyVersion")
    parent_concept = relationship("Concept", foreign_keys=[parent_concept_id])
    child_concept = relationship("Concept", foreign_keys=[child_concept_id])


# ── Taxonomy Edge Candidates ─────────────────────────────

class TaxonomyEdgeCandidate(Base):
    __tablename__ = "taxonomy_edge_candidates"
    __table_args__ = (
        Index("idx_edge_candidates_taxonomy", "taxonomy_version_id", "created_at"),
        Index("idx_edge_candidates_collection", "collection_id", "created_at"),
        Index("idx_edge_candidates_lang_method", "collection_id", "lang", "method", "decision"),
        Index("idx_edge_candidates_risk", "collection_id", "risk_score"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    taxonomy_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("taxonomy_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"))
    child_concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"))
    parent_label = Column(Text, nullable=False)
    child_label = Column(Text, nullable=False)
    lang = Column(String(10))
    method = Column(String(64), nullable=False, default="unknown")
    stage = Column(String(32), nullable=False, default="build")
    base_score = Column(Float, nullable=False, default=0.0)
    ranker_score = Column(Float)
    evidence_score = Column(Float)
    final_score = Column(Float, nullable=False, default=0.0)
    decision = Column(String(16), nullable=False, default="pending")
    risk_score = Column(Float, nullable=False, default=0.0)
    rejection_reason = Column(Text)
    feature_vector = Column(JSONB, nullable=False, default=dict)
    evidence = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── Taxonomy Edge Labels ─────────────────────────────────

class TaxonomyEdgeLabel(Base):
    __tablename__ = "taxonomy_edge_labels"
    __table_args__ = (
        Index("idx_edge_labels_taxonomy", "taxonomy_version_id", "created_at"),
        Index("idx_edge_labels_collection", "collection_id", "created_at"),
        Index("idx_edge_labels_source", "collection_id", "label_source", "label"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("taxonomy_edge_candidates.id", ondelete="SET NULL"),
    )
    taxonomy_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("taxonomy_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"))
    child_concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"))
    parent_label = Column(Text, nullable=False)
    child_label = Column(Text, nullable=False)
    label = Column(String(16), nullable=False)
    label_source = Column(String(32), nullable=False, default="manual")
    reviewer_id = Column(String(64))
    reason = Column(Text)
    meta = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── Threshold Profiles ───────────────────────────────────

class TaxonomyThresholdProfile(Base):
    __tablename__ = "taxonomy_threshold_profiles"
    __table_args__ = (
        Index("idx_threshold_profiles_collection", "collection_id", "created_at"),
        Index("idx_threshold_profiles_active", "collection_id", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"))
    name = Column(String(128), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    min_samples = Column(Integer, nullable=False, default=50)
    profile = Column(JSONB, nullable=False, default=dict)
    metrics = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow)


# ── Taxonomy Releases ────────────────────────────────────

class TaxonomyRelease(Base):
    __tablename__ = "taxonomy_releases"
    __table_args__ = (
        Index("idx_taxonomy_releases_collection", "collection_id", "created_at"),
        Index("idx_taxonomy_releases_channel_active", "collection_id", "channel", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    taxonomy_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("taxonomy_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    release_name = Column(String(128), nullable=False)
    channel = Column(String(16), nullable=False, default="active")
    traffic_percent = Column(Integer, nullable=False, default=100)
    is_active = Column(Boolean, nullable=False, default=True)
    rollback_of = Column(UUID(as_uuid=True), ForeignKey("taxonomy_releases.id", ondelete="SET NULL"))
    quality_snapshot = Column(JSONB, nullable=False, default=dict)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── Jobs ─────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id"), nullable=False)
    taxonomy_version_id = Column(UUID(as_uuid=True), ForeignKey("taxonomy_versions.id"))
    type = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False, default="QUEUED")
    progress = Column(Integer, nullable=False, default=0)
    error_message = Column(Text)
    current_stage = Column(String(32))
    retry_count = Column(Integer, nullable=False, default=0)
    correlation_id = Column(String(64))
    trace_id = Column(String(64))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


# ── Job Events ───────────────────────────────────────────

class JobEvent(Base):
    __tablename__ = "job_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    ts = Column(DateTime(timezone=True), default=utcnow)
    level = Column(String(16), nullable=False, default="INFO")
    message = Column(Text, nullable=False)
    meta = Column(JSONB, default=dict)


# ── Helper ───────────────────────────────────────────────

def get_session() -> Session:
    return SessionLocal()


# ── Dead Letter Log ──────────────────────────────────────

class DeadLetterLog(Base):
    __tablename__ = "dead_letter_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    queue_name = Column(String(128), nullable=False)
    routing_key = Column(String(128))
    payload = Column(JSONB, default=dict)
    error_message = Column(Text)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
