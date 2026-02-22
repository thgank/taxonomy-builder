-- =====================================================================
-- V4: Quality data loop / model-style taxonomy releases
-- =====================================================================

-- ── Candidate edge logging (active-learning + offline training) ─────
CREATE TABLE IF NOT EXISTS taxonomy_edge_candidates (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    taxonomy_version_id UUID         NOT NULL REFERENCES taxonomy_versions(id) ON DELETE CASCADE,
    collection_id      UUID          NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    parent_concept_id  UUID          REFERENCES concepts(id) ON DELETE SET NULL,
    child_concept_id   UUID          REFERENCES concepts(id) ON DELETE SET NULL,
    parent_label       TEXT          NOT NULL,
    child_label        TEXT          NOT NULL,
    lang               VARCHAR(10),
    method             VARCHAR(64)   NOT NULL DEFAULT 'unknown',
    stage              VARCHAR(32)   NOT NULL DEFAULT 'build',
    base_score         DOUBLE PRECISION NOT NULL DEFAULT 0,
    ranker_score       DOUBLE PRECISION,
    evidence_score     DOUBLE PRECISION,
    final_score        DOUBLE PRECISION NOT NULL DEFAULT 0,
    decision           VARCHAR(16)   NOT NULL DEFAULT 'pending',
    risk_score         DOUBLE PRECISION NOT NULL DEFAULT 0,
    rejection_reason   TEXT,
    feature_vector     JSONB         NOT NULL DEFAULT '{}'::jsonb,
    evidence           JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_edge_candidates_taxonomy
    ON taxonomy_edge_candidates(taxonomy_version_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_edge_candidates_collection
    ON taxonomy_edge_candidates(collection_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_edge_candidates_lang_method
    ON taxonomy_edge_candidates(collection_id, lang, method, decision);
CREATE INDEX IF NOT EXISTS idx_edge_candidates_risk
    ON taxonomy_edge_candidates(collection_id, risk_score DESC);

-- ── Human labels for candidate edges ─────────────────────────────────
CREATE TABLE IF NOT EXISTS taxonomy_edge_labels (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id       UUID REFERENCES taxonomy_edge_candidates(id) ON DELETE SET NULL,
    taxonomy_version_id UUID         NOT NULL REFERENCES taxonomy_versions(id) ON DELETE CASCADE,
    collection_id      UUID          NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    parent_concept_id  UUID          REFERENCES concepts(id) ON DELETE SET NULL,
    child_concept_id   UUID          REFERENCES concepts(id) ON DELETE SET NULL,
    parent_label       TEXT          NOT NULL,
    child_label        TEXT          NOT NULL,
    label              VARCHAR(16)   NOT NULL,
    label_source       VARCHAR(32)   NOT NULL DEFAULT 'manual',
    reviewer_id        VARCHAR(64),
    reason             TEXT,
    meta               JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_edge_labels_taxonomy
    ON taxonomy_edge_labels(taxonomy_version_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_edge_labels_collection
    ON taxonomy_edge_labels(collection_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_edge_labels_source
    ON taxonomy_edge_labels(collection_id, label_source, label);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edge_labels_unique_pair
    ON taxonomy_edge_labels(
        taxonomy_version_id,
        parent_label,
        child_label,
        label_source
    );

-- ── Threshold profiles (versioned adaptive cutoffs) ─────────────────
CREATE TABLE IF NOT EXISTS taxonomy_threshold_profiles (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id      UUID REFERENCES collections(id) ON DELETE CASCADE,
    name               VARCHAR(128)  NOT NULL,
    is_active          BOOLEAN       NOT NULL DEFAULT false,
    min_samples        INT           NOT NULL DEFAULT 50,
    profile            JSONB         NOT NULL DEFAULT '{}'::jsonb,
    metrics            JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_threshold_profiles_collection
    ON taxonomy_threshold_profiles(collection_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_threshold_profiles_active
    ON taxonomy_threshold_profiles(collection_id, is_active)
    WHERE is_active = true;

-- ── Taxonomy releases (active/canary pointers + rollback lineage) ──
CREATE TABLE IF NOT EXISTS taxonomy_releases (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id      UUID         NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    taxonomy_version_id UUID        NOT NULL REFERENCES taxonomy_versions(id) ON DELETE CASCADE,
    release_name       VARCHAR(128) NOT NULL,
    channel            VARCHAR(16)  NOT NULL DEFAULT 'active',
    traffic_percent    INT          NOT NULL DEFAULT 100,
    is_active          BOOLEAN      NOT NULL DEFAULT true,
    rollback_of        UUID         REFERENCES taxonomy_releases(id) ON DELETE SET NULL,
    quality_snapshot   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    notes              TEXT,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_taxonomy_releases_collection
    ON taxonomy_releases(collection_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_taxonomy_releases_channel_active
    ON taxonomy_releases(collection_id, channel, is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_taxonomy_releases_one_active_channel
    ON taxonomy_releases(collection_id, channel)
    WHERE is_active = true;
