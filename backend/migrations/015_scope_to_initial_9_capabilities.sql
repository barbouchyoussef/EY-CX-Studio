BEGIN;

WITH extra_capabilities AS (
  SELECT id
  FROM capabilities
  WHERE code NOT IN (
    'manage_cx_culture',
    'manage_ownership_governance',
    'manage_decision_making',
    'analyze_feedback_collection',
    'analyze_use_of_insights',
    'analyze_channel_consistency',
    'analyze_journey_visibility',
    'improve_measurement_continuous_improvement',
    'improve_acting_on_pain_points'
  )
)
DELETE FROM assessment_answers
WHERE capability_id IN (SELECT id FROM extra_capabilities);

WITH extra_capabilities AS (
  SELECT id
  FROM capabilities
  WHERE code NOT IN (
    'manage_cx_culture',
    'manage_ownership_governance',
    'manage_decision_making',
    'analyze_feedback_collection',
    'analyze_use_of_insights',
    'analyze_channel_consistency',
    'analyze_journey_visibility',
    'improve_measurement_continuous_improvement',
    'improve_acting_on_pain_points'
  )
)
DELETE FROM assessment_insights
WHERE capability_id IN (SELECT id FROM extra_capabilities);

WITH extra_capabilities AS (
  SELECT id
  FROM capabilities
  WHERE code NOT IN (
    'manage_cx_culture',
    'manage_ownership_governance',
    'manage_decision_making',
    'analyze_feedback_collection',
    'analyze_use_of_insights',
    'analyze_channel_consistency',
    'analyze_journey_visibility',
    'improve_measurement_continuous_improvement',
    'improve_acting_on_pain_points'
  )
)
DELETE FROM assessment_scores
WHERE capability_id IN (SELECT id FROM extra_capabilities);

WITH extra_capabilities AS (
  SELECT id
  FROM capabilities
  WHERE code NOT IN (
    'manage_cx_culture',
    'manage_ownership_governance',
    'manage_decision_making',
    'analyze_feedback_collection',
    'analyze_use_of_insights',
    'analyze_channel_consistency',
    'analyze_journey_visibility',
    'improve_measurement_continuous_improvement',
    'improve_acting_on_pain_points'
  )
)
DELETE FROM recommendation_outputs
WHERE capability_id IN (SELECT id FROM extra_capabilities);

WITH extra_capabilities AS (
  SELECT id
  FROM capabilities
  WHERE code NOT IN (
    'manage_cx_culture',
    'manage_ownership_governance',
    'manage_decision_making',
    'analyze_feedback_collection',
    'analyze_use_of_insights',
    'analyze_channel_consistency',
    'analyze_journey_visibility',
    'improve_measurement_continuous_improvement',
    'improve_acting_on_pain_points'
  )
)
DELETE FROM capability_maturity_rubrics
WHERE capability_id IN (SELECT id FROM extra_capabilities);

WITH extra_capabilities AS (
  SELECT id
  FROM capabilities
  WHERE code NOT IN (
    'manage_cx_culture',
    'manage_ownership_governance',
    'manage_decision_making',
    'analyze_feedback_collection',
    'analyze_use_of_insights',
    'analyze_channel_consistency',
    'analyze_journey_visibility',
    'improve_measurement_continuous_improvement',
    'improve_acting_on_pain_points'
  )
)
DELETE FROM capability_recommendations
WHERE capability_id IN (SELECT id FROM extra_capabilities);

DELETE FROM capabilities
WHERE code NOT IN (
  'manage_cx_culture',
  'manage_ownership_governance',
  'manage_decision_making',
  'analyze_feedback_collection',
  'analyze_use_of_insights',
  'analyze_channel_consistency',
  'analyze_journey_visibility',
  'improve_measurement_continuous_improvement',
  'improve_acting_on_pain_points'
);

COMMIT;
