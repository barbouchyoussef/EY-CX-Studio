BEGIN;

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS prompt_profile VARCHAR(40) NOT NULL DEFAULT 'consultant_guided';

COMMIT;

