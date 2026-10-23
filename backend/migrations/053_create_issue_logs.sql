-- A saved Issue Log: a named consolidation of findings collected from selected module artifacts
-- (assessment / interview / social / desk). Findings/kpis/sources are stored as JSONB snapshots so
-- the log is stable even if a source is later changed or deleted.
CREATE TABLE IF NOT EXISTS issue_logs (
    id          SERIAL PRIMARY KEY,
    owner_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    project_id  INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    name        VARCHAR(255) NOT NULL,
    findings    JSONB NOT NULL DEFAULT '[]'::jsonb,
    kpis        JSONB NOT NULL DEFAULT '{}'::jsonb,
    sources     JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_issue_logs_owner   ON issue_logs(owner_id);
CREATE INDEX IF NOT EXISTS idx_issue_logs_project ON issue_logs(project_id);
