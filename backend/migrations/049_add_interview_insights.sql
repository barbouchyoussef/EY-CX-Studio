-- Persist the LLM cross-reference "insights" briefing on the guide so history can show it
-- without regenerating (it was previously computed and thrown away). Shape:
--   { "markdown": "...", "generated_at": "iso8601", "generated_by": <user id> }
ALTER TABLE interview_guides ADD COLUMN IF NOT EXISTS insights JSONB;
