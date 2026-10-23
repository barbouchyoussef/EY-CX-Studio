BEGIN;

UPDATE capabilities
SET
  description = NULLIF(BTRIM(description), ''),
  evidence_required = NULLIF(BTRIM(evidence_required), ''),
  question_guidelines = NULLIF(BTRIM(question_guidelines), '');

UPDATE capability_recommendations
SET
  recommendation_guideline = BTRIM(recommendation_guideline),
  priority_hint = NULLIF(LOWER(BTRIM(priority_hint)), ''),
  consultant_note = NULLIF(BTRIM(consultant_note), ''),
  evidence_to_cite = NULLIF(BTRIM(evidence_to_cite), ''),
  initiative_suggestions = NULLIF(BTRIM(initiative_suggestions), ''),
  business_impact = NULLIF(BTRIM(business_impact), ''),
  tone_hint = NULLIF(LOWER(BTRIM(tone_hint)), '');

UPDATE capability_recommendations
SET tone_hint = 'balanced'
WHERE tone_hint IS NULL
   OR tone_hint NOT IN ('direct', 'balanced', 'executive');

UPDATE capability_recommendations
SET priority_hint = 'build_consistency'
WHERE priority_hint IS NULL
   OR priority_hint NOT IN ('urgent_foundation', 'build_consistency', 'scale_advantage');

COMMIT;
