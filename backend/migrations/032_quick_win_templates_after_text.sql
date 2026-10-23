BEGIN;

ALTER TABLE capability_quick_win_templates
ADD COLUMN IF NOT EXISTS after_text TEXT;

UPDATE capability_quick_win_templates qwt
SET after_text = NULLIF(BTRIM(cr.business_impact), '')
FROM capability_recommendations cr
WHERE cr.capability_id = qwt.capability_id
  AND cr.maturity_level_id = qwt.maturity_level_id
  AND qwt.after_text IS NULL
  AND NULLIF(BTRIM(cr.business_impact), '') IS NOT NULL;

COMMIT;
