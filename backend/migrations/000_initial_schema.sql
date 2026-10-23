BEGIN;

CREATE TABLE IF NOT EXISTS sectors (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS company_sizes (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS maturity_levels (
  id BIGSERIAL PRIMARY KEY,
  level_number SMALLINT NOT NULL UNIQUE CHECK (level_number >= 1),
  label VARCHAR(50) NOT NULL,
  description TEXT
);

CREATE TABLE IF NOT EXISTS axes (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(20) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  sort_order INTEGER NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS companies (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(255),
  sector_id BIGINT REFERENCES sectors(id),
  size_id BIGINT REFERENCES company_sizes(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS capabilities (
  id BIGSERIAL PRIMARY KEY,
  axis_id BIGINT NOT NULL REFERENCES axes(id) ON DELETE CASCADE,
  code VARCHAR(100) NOT NULL UNIQUE,
  name VARCHAR(150) NOT NULL,
  description TEXT,
  evidence_required TEXT,
  question_guidelines TEXT,
  sort_order INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS capability_maturity_rubrics (
  id BIGSERIAL PRIMARY KEY,
  capability_id BIGINT NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
  maturity_level_id BIGINT NOT NULL REFERENCES maturity_levels(id) ON DELETE CASCADE,
  description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT capability_maturity_rubrics_capability_id_maturity_level_id_key
    UNIQUE (capability_id, maturity_level_id)
);

CREATE TABLE IF NOT EXISTS capability_recommendations (
  id BIGSERIAL PRIMARY KEY,
  capability_id BIGINT NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
  maturity_level_id BIGINT NOT NULL REFERENCES maturity_levels(id) ON DELETE CASCADE,
  recommendation_guideline TEXT NOT NULL,
  priority_hint VARCHAR(40),
  consultant_note TEXT,
  evidence_to_cite TEXT,
  initiative_suggestions TEXT,
  business_impact TEXT,
  tone_hint VARCHAR(40),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT capability_recommendations_capability_id_maturity_level_id_key
    UNIQUE (capability_id, maturity_level_id)
);

CREATE TABLE IF NOT EXISTS assessments (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id),
  current_axis_id BIGINT REFERENCES axes(id),
  overall_maturity_level_id BIGINT REFERENCES maturity_levels(id),
  overall_maturity_band VARCHAR(40),
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  state_version INTEGER NOT NULL DEFAULT 1,
  current_axis_question_count INTEGER NOT NULL DEFAULT 0,
  current_axis_low_quality_count INTEGER NOT NULL DEFAULT 0,
  pending_followup_hint VARCHAR(255),
  pending_question VARCHAR(1000),
  conversation_stage VARCHAR(30) NOT NULL DEFAULT 'intro',
  clarification_count INTEGER NOT NULL DEFAULT 0,
  prompt_profile VARCHAR(40) NOT NULL DEFAULT 'consultant_guided',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT assessments_status_check
    CHECK (status IN ('active', 'completed', 'paused', 'archived'))
);

CREATE TABLE IF NOT EXISTS assessment_scores (
  id BIGSERIAL PRIMARY KEY,
  assessment_id BIGINT NOT NULL REFERENCES assessments(id),
  capability_id BIGINT NOT NULL REFERENCES capabilities(id),
  maturity_level_id BIGINT NOT NULL REFERENCES maturity_levels(id),
  confidence NUMERIC(4,3),
  justification TEXT,
  overridden BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT assessment_scores_assessment_id_capability_id_key
    UNIQUE (assessment_id, capability_id),
  CONSTRAINT assessment_scores_confidence_check
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE TABLE IF NOT EXISTS assessment_answers (
  id BIGSERIAL PRIMARY KEY,
  assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  capability_id BIGINT REFERENCES capabilities(id),
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assessment_axis_memory (
  id BIGSERIAL PRIMARY KEY,
  assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  axis VARCHAR(50) NOT NULL,
  summary TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_assessment_axis_memory UNIQUE (assessment_id, axis)
);

CREATE TABLE IF NOT EXISTS assessment_idempotency (
  id BIGSERIAL PRIMARY KEY,
  assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  idempotency_key VARCHAR(128) NOT NULL,
  response_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_assessment_idempotency UNIQUE (assessment_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS assessment_insights (
  id BIGSERIAL PRIMARY KEY,
  assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  capability_id BIGINT REFERENCES capabilities(id),
  insight_text TEXT NOT NULL,
  maturity_level_id BIGINT REFERENCES maturity_levels(id),
  confidence NUMERIC(4,3),
  justification TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT assessment_insights_confidence_check
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE TABLE IF NOT EXISTS recommendation_outputs (
  id BIGSERIAL PRIMARY KEY,
  assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  capability_id BIGINT REFERENCES capabilities(id),
  maturity_level_id BIGINT REFERENCES maturity_levels(id),
  generated_text TEXT NOT NULL,
  priority VARCHAR(40),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_companies_sector_id ON companies(sector_id);
CREATE INDEX IF NOT EXISTS ix_companies_size_id ON companies(size_id);
CREATE INDEX IF NOT EXISTS ix_capabilities_axis_id ON capabilities(axis_id);
CREATE INDEX IF NOT EXISTS ix_assessments_company_id ON assessments(company_id);
CREATE INDEX IF NOT EXISTS ix_assessments_current_axis_id ON assessments(current_axis_id);
CREATE INDEX IF NOT EXISTS ix_assessments_overall_maturity_level_id ON assessments(overall_maturity_level_id);
CREATE INDEX IF NOT EXISTS ix_assessment_scores_assessment_id ON assessment_scores(assessment_id);
CREATE INDEX IF NOT EXISTS ix_assessment_scores_capability_id ON assessment_scores(capability_id);
CREATE INDEX IF NOT EXISTS ix_assessment_scores_maturity_level_id ON assessment_scores(maturity_level_id);
CREATE INDEX IF NOT EXISTS ix_assessment_answers_assessment_id ON assessment_answers(assessment_id);
CREATE INDEX IF NOT EXISTS ix_assessment_answers_capability_id ON assessment_answers(capability_id);
CREATE INDEX IF NOT EXISTS ix_assessment_axis_memory_assessment_id ON assessment_axis_memory(assessment_id);
CREATE INDEX IF NOT EXISTS ix_assessment_axis_memory_axis ON assessment_axis_memory(axis);
CREATE INDEX IF NOT EXISTS idx_assessment_idempotency_assessment_id ON assessment_idempotency(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_insights_assessment_id ON assessment_insights(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_insights_capability_id ON assessment_insights(capability_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_outputs_assessment_id ON recommendation_outputs(assessment_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_outputs_capability_id ON recommendation_outputs(capability_id);

COMMIT;
