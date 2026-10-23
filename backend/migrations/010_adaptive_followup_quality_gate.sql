BEGIN;

ALTER TABLE assessments
ADD COLUMN IF NOT EXISTS current_axis_low_quality_count INT NOT NULL DEFAULT 0;

ALTER TABLE assessments
ADD COLUMN IF NOT EXISTS pending_followup_hint VARCHAR(255);

COMMIT;
