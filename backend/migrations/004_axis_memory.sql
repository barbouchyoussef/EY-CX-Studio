BEGIN;

CREATE TABLE IF NOT EXISTS assessment_axis_memory (
  id SERIAL PRIMARY KEY,
  assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  axis VARCHAR(50) NOT NULL,
  summary TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_assessment_axis_memory') THEN
    ALTER TABLE assessment_axis_memory
      ADD CONSTRAINT uq_assessment_axis_memory UNIQUE (assessment_id, axis);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_assessment_axis_memory_assessment_id ON assessment_axis_memory(assessment_id);
CREATE INDEX IF NOT EXISTS ix_assessment_axis_memory_axis ON assessment_axis_memory(axis);

COMMIT;
