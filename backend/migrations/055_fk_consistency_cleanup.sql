-- FK consistency cleanup (see the schema review):
--   1) assessment_scores didn't cascade with its parent like its sibling child tables -> latent
--      delete failure. Make it CASCADE like assessment_answers/insights/axis_memory.
--   2) companies had duplicate FK constraints on sector_id / size_id (added twice) -> drop the extras.
--   3) Standardize the *nullable* user-ownership FKs to ON DELETE SET NULL, so soft/hard user
--      removal behaves the same everywhere (matches issue_logs / llm_calls / invites).
-- Left intentionally as NO ACTION: projects.owner_id and analysis_shares.shared_by are NOT NULL,
-- so SET NULL is impossible there; a project/share always keeps a real owner (soft-delete users).
-- Re-runnable: DROP IF EXISTS then ADD (the seed runner also tolerates "already exists").

-- 1) assessment_scores -> assessments should cascade.
ALTER TABLE assessment_scores DROP CONSTRAINT IF EXISTS assessment_scores_assessment_id_fkey;
ALTER TABLE assessment_scores ADD CONSTRAINT assessment_scores_assessment_id_fkey
    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE;

-- 2) Drop the duplicate company FK constraints (keep the canonical *_fkey ones).
ALTER TABLE companies DROP CONSTRAINT IF EXISTS fk_companies_sector;
ALTER TABLE companies DROP CONSTRAINT IF EXISTS fk_companies_size;

-- 3) Standardize nullable ownership FKs -> SET NULL.
ALTER TABLE assessments DROP CONSTRAINT IF EXISTS assessments_owner_id_fkey;
ALTER TABLE assessments ADD CONSTRAINT assessments_owner_id_fkey
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE interview_guides DROP CONSTRAINT IF EXISTS interview_guides_owner_id_fkey;
ALTER TABLE interview_guides ADD CONSTRAINT interview_guides_owner_id_fkey
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE project_artifacts DROP CONSTRAINT IF EXISTS project_artifacts_created_by_fkey;
ALTER TABLE project_artifacts ADD CONSTRAINT project_artifacts_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE scraping_jobs DROP CONSTRAINT IF EXISTS scraping_jobs_owner_id_fkey;
ALTER TABLE scraping_jobs ADD CONSTRAINT scraping_jobs_owner_id_fkey
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL;
