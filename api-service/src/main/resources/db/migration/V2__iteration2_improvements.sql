-- =====================================================================
-- V2: Iteration 2 (part 1) — enum extensions
-- =====================================================================

-- ── New enum values ─────────────────────────────────────────────────
ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'EVALUATE';
ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'RETRYING';
