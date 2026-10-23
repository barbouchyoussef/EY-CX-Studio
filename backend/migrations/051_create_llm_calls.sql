-- Observability: one row per LLM API call, for cost + latency + error tracking.
-- Written best-effort from the LLM gateway; a logging failure never blocks the call itself.
-- Powers the Metabase observability dashboard (cost/day, cost per feature, error rate, p95 latency,
-- and cost attributed to a domain object via ref_kind/ref_id).
CREATE TABLE IF NOT EXISTS llm_calls (
    id                BIGSERIAL PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    feature           VARCHAR(60) NOT NULL DEFAULT 'unknown',  -- e.g. 'assessment.coverage', 'social.classify'
    provider          VARCHAR(30) NOT NULL DEFAULT 'mistral',   -- 'mistral' | 'moonshot' | 'gemini' | ...
    model             VARCHAR(80),
    ok                BOOLEAN NOT NULL DEFAULT TRUE,            -- did the call succeed?
    error             VARCHAR(300),                            -- error class/message (truncated) when ok = false
    latency_ms        INTEGER,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    cost_usd          NUMERIC(12, 6),                          -- estimated from a per-model price table
    owner_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- who triggered it (per-user cost)
    ref_kind          VARCHAR(30),                             -- domain object kind: 'assessment', 'scraping_job', ...
    ref_id            VARCHAR(64),                             -- its id, so cost can be attributed per object
    request_id        VARCHAR(40)                              -- groups every call made within one user action
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_created_at ON llm_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_calls_feature    ON llm_calls(feature);
CREATE INDEX IF NOT EXISTS idx_llm_calls_owner      ON llm_calls(owner_id);
