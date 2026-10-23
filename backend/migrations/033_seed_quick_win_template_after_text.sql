BEGIN;

WITH quick_win_rows(code, level_number, quick_win_guideline, after_text, owner_hint, timeline_hint, active) AS (
  VALUES
    (
      'manage_cx_culture',
      1,
      'Launch one practical CX playbook and coach teams on the moments that matter most.',
      'Customer-facing teams get a shared service baseline, reducing inconsistent behaviors and making CX expectations easier to coach.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'manage_cx_culture',
      2,
      'Turn CX culture into recurring coaching and quality feedback across teams.',
      'Customer-focused behaviors become more repeatable through team routines, QA feedback, and visible reinforcement.',
      'cx lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'manage_cx_culture',
      3,
      'Link coaching and recognition to the customer outcomes that matter most.',
      'Teams can connect daily behaviors to measurable customer outcomes, strengthening accountability and cultural consistency.',
      'cx lead',
      'later operationalization',
      TRUE
    ),
    (
      'manage_ownership_governance',
      1,
      'Start one recurring CX review with named owners and blocked-issue escalation.',
      'Customer issues stop depending only on informal follow-up because ownership, escalation, and next actions become visible.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'manage_ownership_governance',
      2,
      'Formalize cross-functional CX reviews with action tracking and leadership follow-up.',
      'Cross-functional teams gain a clearer operating rhythm for customer issues, reducing dropped actions and fragmented accountability.',
      'operations lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'manage_ownership_governance',
      3,
      'Use governance to steer improvement investment and outcome accountability.',
      'CX governance becomes a decision mechanism that connects ownership, investment choices, and measurable customer outcomes.',
      'transformation lead',
      'later operationalization',
      TRUE
    ),
    (
      'manage_decision_making',
      1,
      'Define one simple customer decision forum with a fixed review cadence.',
      'Customer evidence gets a defined place in operational decisions, reducing purely reactive or internally driven prioritization.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'manage_decision_making',
      2,
      'Link customer decisions to named owners, actions, and follow-up checks.',
      'Customer feedback becomes more actionable because decisions are connected to owners, next steps, and visible follow-up.',
      'operations lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'manage_decision_making',
      3,
      'Use structured customer decisions to guide planning and resource choices.',
      'Customer evidence has a stronger path into planning, helping teams prioritize resources around the highest-impact experience gaps.',
      'operations lead',
      'later operationalization',
      TRUE
    ),
    (
      'analyze_feedback_collection',
      1,
      'Set one recurring feedback pulse and one weekly review routine.',
      'Feedback capture becomes less ad hoc, giving teams a repeatable source of customer signals to review and act on.',
      'insights lead',
      'earliest quick win',
      TRUE
    ),
    (
      'analyze_feedback_collection',
      2,
      'Expand feedback collection across the main journeys and review it cross-functionally.',
      'Teams gain broader and more comparable feedback coverage, improving visibility across the main customer touchpoints.',
      'insights lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'analyze_feedback_collection',
      3,
      'Embed customer feedback reviews into regular service and decision routines.',
      'Feedback becomes a normal input into service management, improving continuity between listening, decisions, and action.',
      'cx lead',
      'later operationalization',
      TRUE
    ),
    (
      'analyze_use_of_insights',
      1,
      'Group repeated feedback into simple themes and agree what to investigate first.',
      'Customer comments become easier to interpret because repeated issues are grouped into themes instead of handled only case by case.',
      'insights lead',
      'earliest quick win',
      TRUE
    ),
    (
      'analyze_use_of_insights',
      2,
      'Add root-cause review and customer-impact criteria to the weekly insight routine.',
      'Insight reviews become more decision-ready by connecting repeated themes to causes, impact, and prioritization logic.',
      'insights lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'analyze_use_of_insights',
      3,
      'Use synthesized insights to steer priorities, experiments, and action reviews.',
      'Customer insight becomes a stronger management input, helping teams focus improvement effort where it can shift outcomes.',
      'cx lead',
      'later operationalization',
      TRUE
    ),
    (
      'analyze_channel_consistency',
      1,
      'Define one shared cross-channel service standard for the main customer touchpoints.',
      'Customers receive more consistent information and handoffs because teams have a shared baseline for channel behaviour.',
      'digital lead',
      'earliest quick win',
      TRUE
    ),
    (
      'analyze_channel_consistency',
      2,
      'Review channel handoffs regularly and fix the biggest consistency gaps first.',
      'Cross-channel friction becomes easier to spot and resolve, reducing repeat contacts and inconsistent customer experiences.',
      'operations lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'analyze_channel_consistency',
      3,
      'Use cross-channel standards to steer a more coherent end-to-end experience.',
      'Channel management shifts from local fixes to a more joined-up experience with clearer standards and monitoring.',
      'digital lead',
      'later operationalization',
      TRUE
    ),
    (
      'analyze_journey_visibility',
      1,
      'Document the top journeys and assign one owner to each.',
      'Teams gain a shared view of the most important journeys, making pain points easier to locate and discuss together.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'analyze_journey_visibility',
      2,
      'Review key journeys on a fixed cadence and log the main friction points.',
      'Journey visibility becomes more operational because teams regularly review touchpoints, friction, and ownership.',
      'cx lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'analyze_journey_visibility',
      3,
      'Use owned journeys as the backbone for planning and service decisions.',
      'Journey architecture becomes a practical planning tool, helping leaders connect improvement decisions to customer moments.',
      'operations lead',
      'later operationalization',
      TRUE
    ),
    (
      'improve_measurement_continuous_improvement',
      1,
      'Pick a small set of CX measures and review them on a fixed cadence.',
      'Teams gain a basic improvement rhythm by tracking a focused set of CX measures and discussing what changed.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'improve_measurement_continuous_improvement',
      2,
      'Link CX measures to owners and follow-up actions when scores move.',
      'Measurement becomes more useful because metric movement triggers ownership, action review, and follow-up.',
      'cx lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'improve_measurement_continuous_improvement',
      3,
      'Manage improvement work as a portfolio by customer and business impact.',
      'Improvement activity becomes easier to prioritize and govern through connected CX, operational, and business outcomes.',
      'transformation lead',
      'later operationalization',
      TRUE
    ),
    (
      'improve_acting_on_pain_points',
      1,
      'Introduce one simple root-cause check before closing recurring pain points.',
      'Recurring pain points are less likely to be closed superficially because teams check causes before moving on.',
      'cx lead',
      'earliest quick win',
      TRUE
    ),
    (
      'improve_acting_on_pain_points',
      2,
      'Run recurring pain-point reviews and connect findings to action plans.',
      'Pain-point handling becomes more structured through review routines, owners, and clearer action follow-through.',
      'cx lead',
      'after first routine is in place',
      TRUE
    ),
    (
      'improve_acting_on_pain_points',
      3,
      'Combine pain-point reviews with trend monitoring to catch issues earlier.',
      'Teams move from reactive fixes toward earlier detection and more systematic prevention of recurring customer issues.',
      'transformation lead',
      'later operationalization',
      TRUE
    )
)
INSERT INTO capability_quick_win_templates (
  capability_id,
  maturity_level_id,
  quick_win_guideline,
  after_text,
  owner_hint,
  timeline_hint,
  active
)
SELECT
  c.id,
  ml.id,
  q.quick_win_guideline,
  q.after_text,
  q.owner_hint,
  q.timeline_hint,
  q.active
FROM quick_win_rows q
JOIN capabilities c ON c.code = q.code
JOIN maturity_levels ml ON ml.level_number = q.level_number
ON CONFLICT (capability_id, maturity_level_id)
DO UPDATE SET
  quick_win_guideline = EXCLUDED.quick_win_guideline,
  after_text = EXCLUDED.after_text,
  owner_hint = EXCLUDED.owner_hint,
  timeline_hint = EXCLUDED.timeline_hint,
  active = EXCLUDED.active,
  updated_at = NOW();

COMMIT;
