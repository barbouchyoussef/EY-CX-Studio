-- Create scraping_jobs so a scrape survives the browser.
-- A full run takes up to 8 minutes (3 Apify actors + classification + report generation).
-- Holding an HTTP request open that long dies at any proxy (nginx 60s, ALB 60s, Azure 230s)
-- and loses a run the client already paid Apify for. The job row lets /run return
-- immediately and the browser poll for progress.
CREATE TABLE IF NOT EXISTS scraping_jobs (
    id SERIAL PRIMARY KEY,
    brand_name VARCHAR(255) NOT NULL,
    -- pending | running | succeeded | failed
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Human-readable progress line shown in the UI, e.g. "Classifying 72 reviews".
    progress VARCHAR(255),
    -- The original ScrapeRequest, so a job can be retried or audited after the fact.
    request JSONB NOT NULL,
    -- The finished ScrapingResponse; NULL until the job succeeds.
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scraping_jobs_status ON scraping_jobs(status);
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_created_at ON scraping_jobs(created_at DESC);
