-- Persist the interview's structured issue-log findings on the guide, so the Issue Log module
-- consumes them for free instead of re-running the LLM extraction on every collect.
-- NULL  = never computed;  '[]' = computed, no findings;  [...] = computed with findings.
ALTER TABLE interview_guides ADD COLUMN IF NOT EXISTS cx_findings JSONB;
