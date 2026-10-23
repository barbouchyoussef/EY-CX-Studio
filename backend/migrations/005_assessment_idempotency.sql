BEGIN;

CREATE TABLE IF NOT EXISTS assessment_idempotency (
    id BIGSERIAL PRIMARY KEY,
    assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    idempotency_key VARCHAR(128) NOT NULL,
    response_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_assessment_idempotency UNIQUE (assessment_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_assessment_idempotency_assessment_id
    ON assessment_idempotency(assessment_id);

COMMIT;
