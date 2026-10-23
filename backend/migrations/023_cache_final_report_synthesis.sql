BEGIN;

ALTER TABLE assessments
ADD COLUMN IF NOT EXISTS executive_summary_text TEXT;

ALTER TABLE assessments
ADD COLUMN IF NOT EXISTS priority_message_text TEXT;

COMMIT;
