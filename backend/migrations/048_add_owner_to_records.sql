-- Ownership on the DB-backed result records so "what can this user see" is answerable.
-- Nullable: legacy rows (created before auth) stay NULL and are treated as admin-only.
ALTER TABLE assessments      ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id);
ALTER TABLE interview_guides ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id);
ALTER TABLE scraping_jobs    ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id);

CREATE INDEX IF NOT EXISTS idx_assessments_owner_id ON assessments(owner_id);
CREATE INDEX IF NOT EXISTS idx_interview_guides_owner_id ON interview_guides(owner_id);
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_owner_id ON scraping_jobs(owner_id);
