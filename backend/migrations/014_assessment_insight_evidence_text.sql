BEGIN;

ALTER TABLE assessment_insights
ADD COLUMN IF NOT EXISTS evidence_text TEXT;

COMMIT;
