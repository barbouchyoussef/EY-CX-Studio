BEGIN;

CREATE TABLE IF NOT EXISTS capability_quick_win_templates (
    id SERIAL PRIMARY KEY,
    capability_id INTEGER NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
    maturity_level_id INTEGER NOT NULL REFERENCES maturity_levels(id) ON DELETE CASCADE,
    quick_win_guideline TEXT NOT NULL,
    owner_hint TEXT,
    timeline_hint TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT capability_quick_win_templates_capability_id_maturity_level_id_key
        UNIQUE (capability_id, maturity_level_id)
);

CREATE INDEX IF NOT EXISTS idx_capability_quick_win_templates_capability_id
    ON capability_quick_win_templates (capability_id);

CREATE INDEX IF NOT EXISTS idx_capability_quick_win_templates_maturity_level_id
    ON capability_quick_win_templates (maturity_level_id);

WITH quick_win_rows(code, level_number, quick_win_guideline, owner_hint, timeline_hint, active) AS (
  VALUES
    (
      'manage_cx_culture',
      1,
      'Launch one practical CX playbook and coach teams on the moments that matter most.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'manage_cx_culture',
      2,
      'Turn CX culture into recurring coaching and quality feedback across teams.',
      'cx lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'manage_cx_culture',
      3,
      'Link coaching and recognition to the customer outcomes that matter most.',
      'cx lead',
      'later operationalization',
      TRUE
    ),
    (
      'manage_ownership_governance',
      1,
      'Start one recurring CX review with named owners and blocked-issue escalation.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'manage_ownership_governance',
      2,
      'Formalize cross-functional CX reviews with action tracking and leadership follow-up.',
      'operations lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'manage_ownership_governance',
      3,
      'Use governance to steer improvement investment and outcome accountability.',
      'transformation lead',
      'later operationalization',
      TRUE
    ),
    (
      'manage_decision_making',
      1,
      'Define one simple customer decision forum with a fixed review cadence.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'manage_decision_making',
      2,
      'Link customer decisions to named owners, actions, and follow-up checks.',
      'operations lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'manage_decision_making',
      3,
      'Use structured customer decisions to guide planning and resource choices.',
      'operations lead',
      'later operationalization',
      TRUE
    ),
    (
      'analyze_feedback_collection',
      1,
      'Set one recurring feedback pulse and one weekly review routine.',
      'insights lead',
      'earliest quick win',
      TRUE
    ),
    (
      'analyze_feedback_collection',
      2,
      'Expand feedback collection across the main journeys and review it cross-functionally.',
      'insights lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'analyze_feedback_collection',
      3,
      'Embed customer feedback reviews into regular service and decision routines.',
      'cx lead',
      'later operationalization',
      TRUE
    ),
    (
      'analyze_use_of_insights',
      1,
      'Pick a small set of CX measures and review them on a fixed cadence.',
      'insights lead',
      'earliest quick win',
      TRUE
    ),
    (
      'analyze_use_of_insights',
      2,
      'Link CX measures to owners and follow-up actions when scores move.',
      'insights lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'analyze_use_of_insights',
      3,
      'Use CX measures in a broader dashboard that steers priorities and decisions.',
      'cx lead',
      'later operationalization',
      TRUE
    ),
    (
      'analyze_channel_consistency',
      1,
      'Define one shared cross-channel service standard for the main customer touchpoints.',
      'digital lead',
      'earliest quick win',
      TRUE
    ),
    (
      'analyze_channel_consistency',
      2,
      'Review channel handoffs regularly and fix the biggest consistency gaps first.',
      'operations lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'analyze_channel_consistency',
      3,
      'Use cross-channel standards to steer a more coherent end-to-end experience.',
      'digital lead',
      'later operationalization',
      TRUE
    ),
    (
      'analyze_journey_visibility',
      1,
      'Document the top journeys and assign one owner to each.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'analyze_journey_visibility',
      2,
      'Review key journeys on a fixed cadence and log the main friction points.',
      'cx lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'analyze_journey_visibility',
      3,
      'Use owned journeys as the backbone for planning and service decisions.',
      'operations lead',
      'later operationalization',
      TRUE
    ),
    (
      'improve_measurement_continuous_improvement',
      1,
      'Create one shared improvement backlog with owner, due date, and status.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'improve_measurement_continuous_improvement',
      2,
      'Run a regular improvement review to reprioritize actions and verify progress.',
      'cx lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'improve_measurement_continuous_improvement',
      3,
      'Manage improvement work as a portfolio by customer and business impact.',
      'transformation lead',
      'later operationalization',
      TRUE
    ),
    (
      'improve_acting_on_pain_points',
      1,
      'Introduce one simple root-cause check before closing recurring pain points.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'improve_acting_on_pain_points',
      2,
      'Run recurring pain-point reviews and connect findings to action plans.',
      'cx lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'improve_acting_on_pain_points',
      3,
      'Combine pain-point reviews with trend monitoring to catch issues earlier.',
      'transformation lead',
      'later operationalization',
      TRUE
    )
)
INSERT INTO capability_quick_win_templates (
  capability_id,
  maturity_level_id,
  quick_win_guideline,
  owner_hint,
  timeline_hint,
  active
)
SELECT
  c.id,
  ml.id,
  q.quick_win_guideline,
  q.owner_hint,
  q.timeline_hint,
  q.active
FROM quick_win_rows q
JOIN capabilities c ON c.code = q.code
JOIN maturity_levels ml ON ml.level_number = q.level_number
ON CONFLICT (capability_id, maturity_level_id)
DO UPDATE SET
  quick_win_guideline = EXCLUDED.quick_win_guideline,
  owner_hint = EXCLUDED.owner_hint,
  timeline_hint = EXCLUDED.timeline_hint,
  active = EXCLUDED.active,
  updated_at = NOW();

COMMIT;
