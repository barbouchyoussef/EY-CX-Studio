BEGIN;

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

CREATE INDEX IF NOT EXISTS ix_capability_recommendations_capability_id
  ON capability_recommendations(capability_id);

CREATE INDEX IF NOT EXISTS ix_capability_recommendations_maturity_level_id
  ON capability_recommendations(maturity_level_id);

COMMIT;
