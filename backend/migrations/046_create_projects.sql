-- Projects move from JSON files to Postgres so they can carry ownership + membership and be
-- queried ("what can this user see"). A project is the collaboration anchor: it owns members,
-- per-step status, and links (artifacts) to the results produced in each step.

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    company_name VARCHAR(255),
    sector VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_owner_id ON projects(owner_id);

-- Who can see/work on a project. The owner is also inserted here with role 'owner'.
CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'collaborator',   -- 'owner' | 'collaborator'
    added_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    PRIMARY KEY (project_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_project_members_user_id ON project_members(user_id);

-- Per-step status map (one row per pipeline step).
CREATE TABLE IF NOT EXISTS project_steps (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    step_key VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'todo',         -- 'todo' | 'in_progress' | 'done'
    PRIMARY KEY (project_id, step_key)
);

-- A produced result attached to a project/step. ref_id is VARCHAR to hold every id scheme:
-- assessment/interview int PKs (as text), desk session ids, social report filenames.
CREATE TABLE IF NOT EXISTS project_artifacts (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    step_key VARCHAR(40) NOT NULL,
    kind VARCHAR(40) NOT NULL,          -- 'assessment' | 'interview_guide' | 'desk_session' | 'social_report'
    ref_id VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_project_artifacts_project_id ON project_artifacts(project_id);
CREATE INDEX IF NOT EXISTS idx_project_artifacts_ref ON project_artifacts(kind, ref_id);
