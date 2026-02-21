-- =====================================================================
-- V1: Taxonomy Builder — initial schema
-- =====================================================================

-- ── Extensions ──────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for fuzzy / LIKE search

-- ── ENUM types ──────────────────────────────────────────────────────
CREATE TYPE document_status  AS ENUM ('NEW','PARSED','FAILED');
CREATE TYPE taxonomy_status  AS ENUM ('NEW','RUNNING','READY','FAILED');
CREATE TYPE job_type         AS ENUM ('IMPORT','NLP','TERMS','TAXONOMY','FULL_PIPELINE');
CREATE TYPE job_status       AS ENUM ('QUEUED','RUNNING','SUCCESS','FAILED','CANCELLED');

-- ── collections ─────────────────────────────────────────────────────
CREATE TABLE collections (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ── documents ───────────────────────────────────────────────────────
CREATE TABLE documents (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id UUID             NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    filename      VARCHAR(512)     NOT NULL,
    mime_type     VARCHAR(128)     NOT NULL,
    size_bytes    BIGINT           NOT NULL DEFAULT 0,
    storage_path  TEXT,
    status        document_status  NOT NULL DEFAULT 'NEW',
    created_at    TIMESTAMPTZ      NOT NULL DEFAULT now(),
    parsed_at     TIMESTAMPTZ
);
CREATE INDEX idx_documents_collection ON documents(collection_id);

-- ── document_chunks ─────────────────────────────────────────────────
CREATE TABLE document_chunks (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id  UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INT         NOT NULL,
    text         TEXT        NOT NULL,
    lang         VARCHAR(10),
    char_start   INT,
    char_end     INT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);

-- Full-text search index on chunk text
ALTER TABLE document_chunks ADD COLUMN tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED;
CREATE INDEX idx_chunks_tsv ON document_chunks USING GIN(tsv);

-- ── concepts ────────────────────────────────────────────────────────
CREATE TABLE concepts (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id UUID         NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    canonical     TEXT         NOT NULL,
    surface_forms JSONB        NOT NULL DEFAULT '[]'::jsonb,
    lang          VARCHAR(10),
    score         DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_concepts_collection_canonical
    ON concepts(collection_id, canonical);

-- ── concept_occurrences ─────────────────────────────────────────────
CREATE TABLE concept_occurrences (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    concept_id   UUID             NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    chunk_id     UUID             NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    snippet      TEXT,
    start_offset INT,
    end_offset   INT,
    confidence   DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE INDEX idx_occurrences_concept ON concept_occurrences(concept_id);
CREATE INDEX idx_occurrences_chunk   ON concept_occurrences(chunk_id);

-- ── taxonomy_versions ───────────────────────────────────────────────
CREATE TABLE taxonomy_versions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id UUID            NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    algorithm     VARCHAR(64)     NOT NULL DEFAULT 'hybrid',
    parameters    JSONB           NOT NULL DEFAULT '{}'::jsonb,
    status        taxonomy_status NOT NULL DEFAULT 'NEW',
    created_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);
CREATE INDEX idx_taxver_collection ON taxonomy_versions(collection_id);

-- ── taxonomy_edges ──────────────────────────────────────────────────
CREATE TABLE taxonomy_edges (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    taxonomy_version_id  UUID             NOT NULL REFERENCES taxonomy_versions(id) ON DELETE CASCADE,
    parent_concept_id    UUID             NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    child_concept_id     UUID             NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    relation             VARCHAR(32)      NOT NULL DEFAULT 'is_a',
    score                DOUBLE PRECISION NOT NULL DEFAULT 0,
    evidence             JSONB            NOT NULL DEFAULT '[]'::jsonb,
    created_at           TIMESTAMPTZ      NOT NULL DEFAULT now(),
    UNIQUE (taxonomy_version_id, parent_concept_id, child_concept_id)
);
CREATE INDEX idx_edges_taxver_parent ON taxonomy_edges(taxonomy_version_id, parent_concept_id);
CREATE INDEX idx_edges_taxver_child  ON taxonomy_edges(taxonomy_version_id, child_concept_id);

-- ── jobs ────────────────────────────────────────────────────────────
CREATE TABLE jobs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id       UUID       NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    taxonomy_version_id UUID       REFERENCES taxonomy_versions(id) ON DELETE SET NULL,
    type                job_type   NOT NULL,
    status              job_status NOT NULL DEFAULT 'QUEUED',
    progress            INT        NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ
);
CREATE INDEX idx_jobs_collection ON jobs(collection_id);

-- ── job_events ──────────────────────────────────────────────────────
CREATE TABLE job_events (
    id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id  UUID         NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    ts      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    level   VARCHAR(16)  NOT NULL DEFAULT 'INFO',
    message TEXT         NOT NULL,
    meta    JSONB        NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_job_events_job ON job_events(job_id);
