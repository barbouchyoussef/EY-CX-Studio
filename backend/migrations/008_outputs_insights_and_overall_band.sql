BEGIN;

ALTER TABLE assessments
ADD COLUMN IF NOT EXISTS overall_maturity_band VARCHAR(40);

CREATE TABLE IF NOT EXISTS assessment_insights (
    id BIGSERIAL PRIMARY KEY,
    assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    capability_id BIGINT REFERENCES capabilities(id),
    insight_text TEXT NOT NULL,
    maturity_level_id BIGINT REFERENCES maturity_levels(id),
    confidence NUMERIC(4,3),
    justification TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assessment_insights_assessment_id
    ON assessment_insights(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_insights_capability_id
    ON assessment_insights(capability_id);

CREATE TABLE IF NOT EXISTS recommendation_outputs (
    id BIGSERIAL PRIMARY KEY,
    assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    capability_id BIGINT REFERENCES capabilities(id),
    maturity_level_id BIGINT REFERENCES maturity_levels(id),
    generated_text TEXT NOT NULL,
    priority VARCHAR(40),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recommendation_outputs_assessment_id
    ON recommendation_outputs(assessment_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_outputs_capability_id
    ON recommendation_outputs(capability_id);

COMMIT;
