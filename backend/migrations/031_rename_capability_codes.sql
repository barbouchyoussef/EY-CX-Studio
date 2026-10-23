BEGIN;

WITH capability_map(old_code, new_code, new_name, new_description, new_evidence_required, new_question_guidelines, new_sort_order, axis_code) AS (
  VALUES
    (
      'manage.feedback_collection',
      'analyze_feedback_collection',
      'Feedback collection',
      'How systematically the organization captures customer feedback across touchpoints.',
      'email inbox, shared mailbox, survey response, CRM case, complaint log, call notes, feedback form, one logging location, tagging, routing to the right team, weekly review of collected feedback',
      'Assess how customer feedback is captured and brought into one place. Focus on whether feedback is collected only through a few basic channels, whether it is logged or routed through some shared tools or review routines, or whether it is systematically captured across touchpoints with clear ownership, tagging, and review cadence. Prefer this capability when the answer explains how feedback is gathered, logged, stored, routed, or reviewed. Do not treat inconsistent answers, poor handoffs, repeated customer effort, or lack of shared context across channels as sufficient evidence for this capability unless the answer also explains how feedback itself is captured or logged.',
      10,
      'analyze'
    ),
    (
      'manage.ticketing_process',
      'manage_ownership_governance',
      'Ownership and governance',
      'Whether CX has clear accountable owners and cross-functional operating mechanisms.',
      'named owner, CX lead or central team, role definition, governance meeting, review cadence, escalation path, follow-up tracker, action log, cross-functional coordination routine, visible accountability for customer issues',
      'Assess how accountability for customer-related issues is organized. Focus on whether ownership is informal, held by a central role or team, or managed through recurring governance with follow-up tracking and coordination across functions. Treat named owners, recurring review routines, follow-up coordination, governance cadence, and visible accountability as strong evidence for this capability, even when the process is still partial or not yet fully cross-functional.',
      20,
      'manage'
    ),
    (
      'manage.customer_journeys',
      'analyze_journey_visibility',
      'Journey visibility',
      'How clearly the organization understands end-to-end journeys and pain points.',
      'shared journey map, service blueprint, touchpoint inventory, journey owner, journey KPI dashboard, regular journey review, cross-functional workshop notes, pain-point register, no shared end-to-end view, teams only see their own touchpoint',
      'Assess how visible the end-to-end customer journey is. Focus on whether teams rely on isolated touchpoint knowledge, only see their own part of the experience, or lack a shared end-to-end journey view, map, or review routine; whether they have partial journey maps or pain-point reviews; or whether they systematically manage journeys with owners, shared artifacts, and pain-point tracking.',
      30,
      'analyze'
    ),
    (
      'analyze.kpis',
      'improve_measurement_continuous_improvement',
      'Measurement and continuous improvement',
      'How CX, operations, and business outcomes are measured and improved over time.',
      'Metrics; targets; review rhythm; actions triggered; business linkage; experiments; before/after results.',
      'Assess how CX improvement is measured over time. Focus on whether metrics are absent or isolated, partially reviewed with some actions, or systematically linked to targets, business outcomes, experiments, and learning loops.',
      10,
      'improve'
    ),
    (
      'analyze.segmentation',
      'analyze_use_of_insights',
      'Use of insights',
      'How feedback becomes actionable insight and informs priorities.',
      'theme review, issue clustering, root cause analysis, prioritization logic, severity criteria, customer impact criteria, decision on what to act on first, insight review meeting, repeated issue patterns, problem prioritization, action prioritization',
      'Assess how feedback is turned into insight and used to decide what matters most. Focus on whether teams only review or observe feedback informally, whether they group issues into themes or repeated patterns, whether they identify root causes, and whether they use explicit logic such as customer impact, frequency, severity, or business importance to decide which issues to act on first. Prefer this capability when the answer explains how the organization interprets feedback, identifies patterns, prioritizes issues, or chooses what to address first. Do not treat feedback being logged in one place, collected through several channels, routed to a shared tool, or reviewed on a regular cadence as sufficient evidence for this capability unless the answer also explains how issues are analyzed, compared, or prioritized.',
      20,
      'analyze'
    ),
    (
      'analyze.root_cause',
      'analyze_channel_consistency',
      'Channel consistency',
      'How consistently CX is managed across customer-facing channels.',
      'Channel standards; handoff process; shared data; consistency checks; examples of fixes.',
      'Assess how consistent the customer experience is across channels. Focus on whether channels operate separately, have partial standards or handoffs, or are managed end-to-end with shared customer context and active consistency monitoring.',
      30,
      'analyze'
    ),
    (
      'improve.improvement_loop',
      'improve_acting_on_pain_points',
      'Acting on pain points',
      'How the organization prioritizes and resolves CX pain points.',
      'pain-point backlog, Jira ticket, Trello card, named owner, due date, action status, closure evidence, customer complaint log, post-fix validation note',
      'Assess how customer pain points are acted on. Focus on whether issues are handled reactively, tracked through a partial backlog or owner process, or managed through a systematic improvement loop with prioritization, closure, and validation.',
      20,
      'improve'
    ),
    (
      'improve.training',
      'manage_cx_culture',
      'CX culture',
      'Whether customer-centric behavior is embedded in leadership, employee routines, and incentives.',
      'manager coaching, team huddle on customer feedback, customer story shared with staff, training on customer-focused behaviours, service standards used in daily work, QA feedback on customer handling, recognition for customer-focused actions, onboarding guidance on customer expectations, performance expectations tied to customer focus',
      'Assess how customer-focused behaviours are reinforced in day-to-day work. Focus on coaching, recognition, training, service standards, QA feedback, leadership rituals, customer stories, and performance expectations that help teams act in a customer-focused way. Do not treat ownership, governance routines, review cadence, or named leads alone as sufficient evidence for this capability unless the answer also shows how customer-focused behaviours are actively encouraged, coached, recognized, or reinforced across teams.',
      10,
      'manage'
    ),
    (
      'improve.governance',
      'manage_decision_making',
      'Decision-making',
      'Whether customer evidence changes strategic and operational decisions.',
      'customer feedback summary, complaint trend, decision log, leadership meeting minutes, prioritization note, roadmap update, policy change note, budget allocation note, named decision owner',
      'Assess how customer feedback influences decisions. Focus on whether decisions are mostly internal/reactive, sometimes informed by customer evidence, or systematically shaped through governance, owners, records, and follow-up.',
      30,
      'manage'
    )
)
UPDATE capabilities c
SET
  code = m.new_code,
  name = m.new_name,
  description = m.new_description,
  evidence_required = m.new_evidence_required,
  question_guidelines = m.new_question_guidelines,
  sort_order = m.new_sort_order
FROM capability_map m
JOIN axes a ON a.code = m.axis_code
WHERE c.code = m.old_code
  AND c.axis_id = a.id;

COMMIT;
