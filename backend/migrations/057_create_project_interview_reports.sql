-- The project-level interview report: one consolidated write-up across every interview attached
-- to a project, cross-referenced against the Orion self-assessments those interviews came from.
--
-- One row per project, so "generate" and "regenerate" are the same write and the UI only ever has
-- one report to show. Dropping the project takes the report with it.
--
--   overview  -- the structured object the UI lays out (same contract as the desk-research report:
--                the model writes prose, Python computes every figure).
--   markdown  -- a rendering of that object, for the PDF export and anything that wants text.
--   sources   -- {"guide_ids": [...], "assessment_ids": [...]} as they were at generation time, so
--                the UI can say the report is stale when interviews are added or answered since.

CREATE TABLE IF NOT EXISTS project_interview_reports (
    project_id   INTEGER     PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    overview     JSONB       NOT NULL,
    markdown     TEXT        NOT NULL,
    sources      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    generated_by INTEGER     REFERENCES users(id) ON DELETE SET NULL
);
