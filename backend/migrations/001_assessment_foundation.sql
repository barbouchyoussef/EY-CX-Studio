BEGIN;

-- Compatibility foundation for the refactored backend schema.
-- Older versions of the project used criteria / assessment_criteria / messages.
-- The current backend uses capabilities / assessment_scores / assessment_answers.

ALTER TABLE IF EXISTS assessments
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE IF EXISTS capabilities
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS evidence_required TEXT,
ADD COLUMN IF NOT EXISTS question_guidelines TEXT;

ALTER TABLE IF EXISTS assessment_scores
ADD COLUMN IF NOT EXISTS justification TEXT;

ALTER TABLE IF EXISTS assessment_answers
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'assessments'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS ix_assessments_company_id ON assessments(company_id)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS ix_assessments_current_axis_id ON assessments(current_axis_id)';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'capabilities'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS ix_capabilities_axis_id ON capabilities(axis_id)';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'assessment_scores'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS ix_assessment_scores_assessment_id ON assessment_scores(assessment_id)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS ix_assessment_scores_capability_id ON assessment_scores(capability_id)';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'assessment_answers'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS ix_assessment_answers_assessment_id ON assessment_answers(assessment_id)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS ix_assessment_answers_capability_id ON assessment_answers(capability_id)';
    END IF;
END $$;

COMMIT;
