-- Make an issue log its own job row.
--
-- Generating a log reads every selected source separately: a modest engagement is 8-30 LLM
-- calls and several minutes of wall time, well past what a reverse proxy will hold open
-- (nginx and ALB default to 60 s). Holding the HTTP request meant closing the tab threw away
-- work that had already been paid for in tokens.
--
-- The scraping module solved the same problem with scraping_jobs. Here the log row itself is
-- the unit of durability: it is created as `pending`, updated as chunks land, and ends as
-- `completed` or `failed` with its findings attached. One row, visible in the dashboard from
-- the moment the run starts.

ALTER TABLE issue_logs ADD COLUMN IF NOT EXISTS status       VARCHAR(20)  NOT NULL DEFAULT 'completed';
ALTER TABLE issue_logs ADD COLUMN IF NOT EXISTS progress     VARCHAR(255);
ALTER TABLE issue_logs ADD COLUMN IF NOT EXISTS error        TEXT;
ALTER TABLE issue_logs ADD COLUMN IF NOT EXISTS request      JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE issue_logs ADD COLUMN IF NOT EXISTS recommendations JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE issue_logs ADD COLUMN IF NOT EXISTS run          JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE issue_logs ADD COLUMN IF NOT EXISTS finished_at  TIMESTAMPTZ;

-- Existing rows predate jobs and are all finished; the DEFAULT above already covers them.
-- status: pending | running | completed | failed
CREATE INDEX IF NOT EXISTS idx_issue_logs_status ON issue_logs (status);
CREATE INDEX IF NOT EXISTS idx_issue_logs_owner_updated ON issue_logs (owner_id, updated_at DESC);

-- Recommendations were previously tucked inside the `kpis` blob to avoid a migration. Move
-- them to their own column now that we are altering the table anyway, so the export and the
-- API stop reaching through kpis for them.
UPDATE issue_logs
   SET recommendations = COALESCE(kpis->'recommendations', '[]'::jsonb)
 WHERE kpis ? 'recommendations'
   AND recommendations = '[]'::jsonb;
