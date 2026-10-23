-- Client magic-links for the maturity assessment. A consultant creates a recipient (the client
-- they're sending it to); the raw token goes in the emailed/copied link, only its SHA-256 is
-- stored. Passwordless, expiring, revocable. One recipient grants access to exactly one assessment.
CREATE TABLE IF NOT EXISTS assessment_recipients (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    client_name VARCHAR(200),
    client_role VARCHAR(200),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',   -- 'sent' | 'opened' | 'completed' | 'revoked'
    expires_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assessment_recipients_assessment ON assessment_recipients(assessment_id);
