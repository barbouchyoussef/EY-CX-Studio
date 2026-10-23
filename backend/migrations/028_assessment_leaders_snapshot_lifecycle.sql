BEGIN;

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS leaders_snapshot_status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS leaders_snapshot_generated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS leaders_snapshot_error TEXT;

UPDATE assessments
SET
    leaders_snapshot_status = 'completed',
    leaders_snapshot_generated_at = COALESCE(leaders_snapshot_generated_at, updated_at)
WHERE leaders_snapshot_payload IS NOT NULL
  AND (leaders_snapshot_status IS NULL OR leaders_snapshot_status = '');

COMMIT;
