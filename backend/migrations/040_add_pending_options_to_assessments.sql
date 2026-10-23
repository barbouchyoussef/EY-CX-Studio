BEGIN;

-- ============================================================
-- 040: Add pending_options to assessments
-- ============================================================
-- Stores the LLM-generated answer options associated with the pending question

ALTER TABLE assessments ADD COLUMN IF NOT EXISTS pending_options JSONB;

COMMIT;
