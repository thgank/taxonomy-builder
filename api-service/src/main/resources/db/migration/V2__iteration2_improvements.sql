-- =====================================================================
-- V2: Iteration 2 — reliability, concurrency, evaluation, observability
-- =====================================================================

-- ── New enum values ─────────────────────────────────────────────────
ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'EVALUATE';
ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'RETRYING';

-- ── Jobs: stage tracking + retry metadata ───────────────────────────
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS current_stage VARCHAR(32);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS retry_count   INT NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(64);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS trace_id       VARCHAR(64);

-- ── Collections: concurrency guard ──────────────────────────────────
ALTER TABLE collections ADD COLUMN IF NOT EXISTS active_job_id UUID REFERENCES jobs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_collections_active_job ON collections(active_job_id)
    WHERE active_job_id IS NOT NULL;

-- ── Taxonomy versions: quality metrics from evaluation ──────────────
ALTER TABLE taxonomy_versions ADD COLUMN IF NOT EXISTS quality_metrics JSONB NOT NULL DEFAULT '{}'::jsonb;

-- ── Taxonomy edges: approval flag for semi-auto editing ─────────────
ALTER TABLE taxonomy_edges ADD COLUMN IF NOT EXISTS approved BOOLEAN;

-- ── DLQ tracking table ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dead_letter_log (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id       UUID         REFERENCES jobs(id) ON DELETE SET NULL,
    queue_name   VARCHAR(128) NOT NULL,
    routing_key  VARCHAR(128),
    payload      JSONB        NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    retry_count  INT          NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dlq_job ON dead_letter_log(job_id);
CREATE INDEX IF NOT EXISTS idx_dlq_created ON dead_letter_log(created_at);

-- ── Partial unique index: only one active job per collection ────────
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_job_per_collection
    ON jobs(collection_id)
    WHERE status IN ('QUEUED', 'RUNNING', 'RETRYING');
