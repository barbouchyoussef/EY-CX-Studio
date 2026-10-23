-- Create interview_guides table to store generated guides and consultant notes
CREATE TABLE IF NOT EXISTS interview_guides (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER REFERENCES assessments(id) ON DELETE SET NULL,
    company_name VARCHAR(255) NOT NULL,
    profile VARCHAR(100) NOT NULL,
    language VARCHAR(10) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_interview_guides_assessment_id ON interview_guides(assessment_id);
