-- A coarse activity type per LLM call, alongside the specific `feature`.
--   'run'       = a module executing its core pipeline (scoring, classifying, generating)
--   'assistant' = an interactive chat/help assistant inside a module
--   'util'      = small internal helper calls (company classification, intent routing)
-- Lets the dashboard split spend by *what kind of thing* a call was, not only by feature.
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS kind VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_llm_calls_kind ON llm_calls(kind);
