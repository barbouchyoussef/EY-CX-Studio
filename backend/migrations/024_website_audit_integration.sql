BEGIN;

ALTER TABLE companies
ADD COLUMN IF NOT EXISTS region VARCHAR(120);

ALTER TABLE companies
ADD COLUMN IF NOT EXISTS website_url VARCHAR(500);

CREATE TABLE IF NOT EXISTS assessment_website_audits (
  id BIGSERIAL PRIMARY KEY,
  assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  website_url VARCHAR(500) NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'pending',
  payload JSONB,
  error_message TEXT,
  report_path VARCHAR(1000),
  desktop_screenshot_path VARCHAR(1000),
  mobile_screenshot_path VARCHAR(1000),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_assessment_website_audits_assessment_id UNIQUE (assessment_id),
  CONSTRAINT assessment_website_audits_status_check
    CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_assessment_website_audits_assessment_id
  ON assessment_website_audits(assessment_id);

CREATE INDEX IF NOT EXISTS ix_assessment_website_audits_status
  ON assessment_website_audits(status);

COMMIT;
