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
