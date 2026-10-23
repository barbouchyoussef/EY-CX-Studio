BEGIN;

ALTER TABLE assessment_scores
  ALTER COLUMN maturity_level_id DROP NOT NULL;

ALTER TABLE assessment_scores
  ADD COLUMN IF NOT EXISTS assessment_status VARCHAR(30) NOT NULL DEFAULT 'not_assessed';

ALTER TABLE assessment_scores
  ADD COLUMN IF NOT EXISTS last_assessed_at TIMESTAMPTZ NULL;

UPDATE assessment_scores
SET
  assessment_status = CASE
    WHEN confidence IS NOT NULL THEN 'assessed'
    ELSE 'not_assessed'
  END,
  last_assessed_at = CASE
    WHEN confidence IS NOT NULL THEN COALESCE(last_assessed_at, created_at)
    ELSE last_assessed_at
  END,
  maturity_level_id = CASE
    WHEN confidence IS NULL THEN NULL
    ELSE maturity_level_id
  END;

CREATE INDEX IF NOT EXISTS ix_assessment_scores_assessment_status
  ON assessment_scores(assessment_status);

COMMIT;
