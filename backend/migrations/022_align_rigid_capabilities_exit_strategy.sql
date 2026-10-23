BEGIN;

UPDATE capabilities
SET
  question_guidelines = 'Goal: Identify the main owner for cross-functional issues. Ask one clear question about who takes the lead. If a leader is named (e.g., CX Lead), ACCEPT it as sufficient and move on. Do not force the search for sub-owners in other departments.',
  updated_at = NOW()
WHERE id = 2;

UPDATE capabilities
SET
  question_guidelines = 'Goal: Understand how feedback leads to action. Ask for one recent example. If the user is vague, ask who reviewed the info. If they don''t know, mark as Level 1 and move on.',
  updated_at = NOW()
WHERE id = 6;

UPDATE capabilities
SET
  question_guidelines = 'Goal: Map CX metrics. Ask what measures are followed. If the user lists even one (e.g., NPS, complaints), accept it. If they have none, mark as Level 1 and move on.',
  updated_at = NOW()
WHERE id = 8;

UPDATE capability_maturity_rubrics
SET description = COALESCE(description, '') || ' The user may say "I don''t know", "pass", or indicate that the process is informal/absent.'
WHERE maturity_level_id = (
  SELECT id
  FROM maturity_levels
  WHERE level_number = 1
)
AND capability_id IN (2, 5, 6, 8)
AND COALESCE(description, '') NOT LIKE '%The user may say "I don''t know", "pass", or indicate that the process is informal/absent.%';

UPDATE capability_maturity_rubrics
SET description = 'Advanced: Clear accountability exists. A central leader (e.g., CX Lead) or a dedicated team coordinates cross-functionally with clear authority and tracking, even if department-specific owners are not explicitly named.'
WHERE capability_id = 2
AND maturity_level_id = (
  SELECT id
  FROM maturity_levels
  WHERE level_number = 3
);

UPDATE capabilities
SET updated_at = NOW()
WHERE id IN (2, 5, 6, 8);

UPDATE capability_maturity_rubrics
SET updated_at = NOW()
WHERE capability_id IN (2, 5, 6, 8);

COMMIT;
