BEGIN;

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS leaders_snapshot_payload JSONB NULL;

COMMIT;
