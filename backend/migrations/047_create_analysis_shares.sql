-- Per-analysis sharing: hand a single result to a specific consultant, independent of projects.
-- Access to an analysis = you own it OR you're a member of its project OR there's a share here.
CREATE TABLE IF NOT EXISTS analysis_shares (
    id SERIAL PRIMARY KEY,
    kind VARCHAR(40) NOT NULL,          -- same kinds as project_artifacts
    ref_id VARCHAR(255) NOT NULL,
    shared_by INTEGER NOT NULL REFERENCES users(id),
    shared_with INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    UNIQUE (kind, ref_id, shared_with)  -- sharing twice is idempotent
);
CREATE INDEX IF NOT EXISTS idx_analysis_shares_shared_with ON analysis_shares(shared_with);
