BEGIN;

ALTER TABLE assessments 
ADD COLUMN IF NOT EXISTS pending_focus_capability_id INTEGER REFERENCES capabilities(id);

COMMIT;
