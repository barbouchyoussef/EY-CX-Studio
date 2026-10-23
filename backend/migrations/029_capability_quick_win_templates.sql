BEGIN;

CREATE TABLE IF NOT EXISTS capability_quick_win_templates (
    id SERIAL PRIMARY KEY,
    capability_id INTEGER NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
    maturity_level_id INTEGER NOT NULL REFERENCES maturity_levels(id) ON DELETE CASCADE,
    quick_win_guideline TEXT NOT NULL,
    owner_hint TEXT,
    timeline_hint TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT capability_quick_win_templates_capability_id_maturity_level_id_key
        UNIQUE (capability_id, maturity_level_id)
);

CREATE INDEX IF NOT EXISTS idx_capability_quick_win_templates_capability_id
    ON capability_quick_win_templates (capability_id);

CREATE INDEX IF NOT EXISTS idx_capability_quick_win_templates_maturity_level_id
    ON capability_quick_win_templates (maturity_level_id);

COMMIT;
