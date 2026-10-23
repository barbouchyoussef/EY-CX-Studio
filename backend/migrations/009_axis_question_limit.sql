BEGIN;

ALTER TABLE assessments
ADD COLUMN IF NOT EXISTS current_axis_question_count INT NOT NULL DEFAULT 0;

COMMIT;
