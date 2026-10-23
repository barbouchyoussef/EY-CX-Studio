BEGIN;

UPDATE capability_maturity_rubrics
SET
  description = COALESCE(description, '') || ' (Or user explicitly states they do not have this process or do not know).',
  updated_at = NOW()
WHERE maturity_level_id = (
  SELECT id
  FROM maturity_levels
  WHERE level_number = 1
)
AND description NOT LIKE '%Or user explicitly states they do not have this process or do not know%';

COMMIT;
