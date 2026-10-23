BEGIN;

WITH guideline_updates(code, question_guidelines) AS (
  VALUES
    ('manage_cx_culture', 'Goal: understand how customer-focused behaviours are reinforced in day-to-day work. Ask for one recent example of how a team was coached, guided, or recognized for customer impact. If vague, probe only on the routine or artifact used. DO NOT ask multiple questions.'),
    ('manage_ownership_governance', 'Goal: understand how accountability for customer-related issues is organized. Focus on whether ownership is informal, held by a central role or team, or managed through recurring governance with follow-up tracking and coordination across functions. Treat named owners, recurring review routines, follow-up coordination, governance cadence, and visible accountability as strong evidence for this capability, even when the process is still partial or not yet fully cross-functional.'),
    ('manage_decision_making', 'Assess how customer feedback influences decisions. Focus on whether decisions are mostly internal/reactive, sometimes informed by customer evidence, or systematically shaped through governance, owners, records, and follow-up.'),
    ('analyze_feedback_collection', 'Assess how customer feedback is captured and brought into one place. Focus on whether feedback is collected only through a few basic channels, whether it is logged or routed through some shared tools or review routines, or whether it is systematically captured across touchpoints with clear ownership, tagging, and review cadence. Prefer this capability when the answer explains how feedback is gathered, logged, stored, routed, or reviewed. Do not treat inconsistent answers, poor handoffs, repeated customer effort, or lack of shared context across channels as sufficient evidence for this capability unless the answer also explains how feedback itself is captured or logged.'),
    ('analyze_use_of_insights', 'Assess how feedback is turned into insight and used to decide what matters most. Focus on whether teams only review or observe feedback informally, whether they group issues into themes or repeated patterns, whether they identify root causes, and whether they use explicit logic such as customer impact, frequency, severity, or business importance to decide which issues to act on first. Prefer this capability when the answer explains how the organization interprets feedback, identifies patterns, prioritizes issues, or chooses what to address first. Do not treat feedback being logged in one place, collected through several channels, routed to a shared tool, or reviewed on a regular cadence as sufficient evidence for this capability unless the answer also explains how issues are analyzed, compared, or prioritized.'),
    ('analyze_channel_consistency', 'Assess how consistently the customer experience is managed across channels. Focus on whether channels operate separately, have partial standards or handoffs, or are managed end-to-end with shared customer context and active consistency monitoring.'),
    ('analyze_journey_visibility', 'Assess how visible the end-to-end customer journey is. Focus on whether teams rely on isolated touchpoint knowledge, only see their own part of the experience, or lack a shared end-to-end journey view, map, or review routine; whether they have partial journey maps or pain-point reviews; or whether they systematically manage journeys with owners, shared artifacts, and pain-point tracking.'),
    ('improve_measurement_continuous_improvement', 'Assess how CX improvement is measured over time. Focus on whether metrics are absent or isolated, partially reviewed with some actions, or systematically linked to targets, business outcomes, experiments, and learning loops.'),
    ('improve_acting_on_pain_points', 'Assess how customer pain points are acted on. Focus on whether issues are handled reactively, tracked through a partial backlog or owner process, or managed through a systematic improvement loop with prioritization, closure, and validation.')
)
UPDATE capabilities c
SET question_guidelines = g.question_guidelines
FROM guideline_updates g
WHERE c.code = g.code;

WITH rubric_rows(code, level_number, description) AS (
  VALUES
    ('manage_cx_culture', 1, 'Customer-focused behaviours are ad hoc, weakly reinforced, and largely dependent on individual managers or frontline goodwill.'),
    ('manage_cx_culture', 2, 'Some coaching, training, service standards, or recognition exist, but adoption is partial and not yet fully embedded in routines.'),
    ('manage_cx_culture', 3, 'Customer-focused behaviours are actively reinforced through leadership routines, coaching, recognition, practical standards, and quality feedback.'),
    ('manage_ownership_governance', 1, 'Accountability is informal or fragmented, with no consistent owner, governance routine, or follow-up discipline for customer issues.'),
    ('manage_ownership_governance', 2, 'A named owner or central team exists, and some governance routines are in place, but coordination and follow-through are not yet fully reliable.'),
    ('manage_ownership_governance', 3, 'Customer issues are managed through recurring governance, clear owners, escalation paths, action logs, and visible cross-functional accountability.'),
    ('manage_decision_making', 1, 'Customer evidence rarely changes decisions; priorities are mostly internal, reactive, or driven by individual judgement.'),
    ('manage_decision_making', 2, 'Customer evidence influences some decisions, but the practice is partial, siloed, or inconsistent across teams.'),
    ('manage_decision_making', 3, 'Customer evidence systematically shapes decisions through governance, named owners, documented trade-offs, and follow-up.'),
    ('analyze_feedback_collection', 1, 'Feedback is collected inconsistently or through a few isolated channels, with weak logging, ownership, and review rhythm.'),
    ('analyze_feedback_collection', 2, 'Feedback is captured through some defined channels or tools, but coverage, ownership, tagging, and review cadence are inconsistent.'),
    ('analyze_feedback_collection', 3, 'Feedback is captured across key touchpoints through structured channels with clear ownership, tagging, and regular review.'),
    ('analyze_use_of_insights', 1, 'Feedback is observed informally, with little evidence of theme review, root-cause analysis, or explicit prioritization logic.'),
    ('analyze_use_of_insights', 2, 'Some theme review or prioritization exists, but the process is inconsistent and not yet decision-ready.'),
    ('analyze_use_of_insights', 3, 'Feedback is translated into actionable insight through pattern analysis, root-cause work, and clear prioritization criteria.'),
    ('analyze_channel_consistency', 1, 'Channels operate separately, with inconsistent standards, weak handoffs, and limited shared customer context.'),
    ('analyze_channel_consistency', 2, 'Some shared standards or handoff practices exist, but consistency is uneven across the experience.'),
    ('analyze_channel_consistency', 3, 'Channels are managed with shared context, consistent standards, and active monitoring for consistency issues.'),
    ('analyze_journey_visibility', 1, 'Journey visibility is weak or absent; teams mainly see isolated touchpoints rather than the full customer path.'),
    ('analyze_journey_visibility', 2, 'Some journeys are mapped or discussed, but ownership, updates, and pain-point tracking remain inconsistent.'),
    ('analyze_journey_visibility', 3, 'Key journeys are owned, documented, and reviewed cross-functionally to guide prioritization and improvements.'),
    ('improve_measurement_continuous_improvement', 1, 'Measures are limited or disconnected from action, with little evidence of a regular improvement loop.'),
    ('improve_measurement_continuous_improvement', 2, 'Measures are tracked and reviewed, but ownership, targets, and business linkage are incomplete.'),
    ('improve_measurement_continuous_improvement', 3, 'Measures are tied to targets, owners, business outcomes, experiments, and systematic improvement loops.'),
    ('improve_acting_on_pain_points', 1, 'Pain points are handled reactively with little backlog, ownership, closure discipline, or validation.'),
    ('improve_acting_on_pain_points', 2, 'Some backlog or owner process exists, but prioritization and closure discipline are inconsistent.'),
    ('improve_acting_on_pain_points', 3, 'Pain points are managed through a repeatable improvement loop with prioritization, owners, closure checks, and validation.')
)
INSERT INTO capability_maturity_rubrics (capability_id, maturity_level_id, description)
SELECT c.id, ml.id, r.description
FROM rubric_rows r
JOIN capabilities c ON c.code = r.code
JOIN maturity_levels ml ON ml.level_number = r.level_number
ON CONFLICT (capability_id, maturity_level_id)
DO UPDATE SET description = EXCLUDED.description;

WITH recommendation_rows(code, level_number, recommendation_guideline, priority_hint, consultant_note, evidence_to_cite, initiative_suggestions, business_impact, tone_hint) AS (
  VALUES
    ('manage_cx_culture', 1, 'Create one practical CX playbook and coach teams on the behaviours that matter most.', 'urgent_foundation', 'Start with one visible routine.', 'Customer-focused behaviours are ad hoc.', 'CX playbook; manager coaching', 'More consistent service delivery and higher employee confidence.', 'direct'),
    ('manage_cx_culture', 2, 'Turn CX culture into recurring coaching, service standards, and quality feedback across teams.', 'build_consistency', 'Make reinforcement repeatable.', 'Some coaching or standards exist.', 'Recurring coaching; service standards', 'Better consistency and clearer expectations.', 'balanced'),
    ('manage_cx_culture', 3, 'Link coaching and recognition to the customer outcomes the business wants to improve most.', 'scale_advantage', 'Tie culture to outcomes.', 'Customer-focused behaviours are reinforced.', 'Outcome-linked recognition', 'Stronger customer outcomes and better adoption.', 'executive'),
    ('manage_ownership_governance', 1, 'Start one recurring CX review with named owners and blocked-issue escalation.', 'urgent_foundation', 'Create clear accountability.', 'Accountability is informal.', 'CX review cadence; blocked-issue escalation', 'Fewer stalled issues and faster resolution.', 'direct'),
    ('manage_ownership_governance', 2, 'Formalize cross-functional CX reviews with action tracking and leadership follow-up.', 'build_consistency', 'Strengthen follow-through.', 'A central owner exists, but routines are uneven.', 'Action tracker; leadership follow-up', 'Better cross-functional coordination and execution.', 'balanced'),
    ('manage_ownership_governance', 3, 'Use governance to steer improvement investment and outcome accountability.', 'scale_advantage', 'Use governance as a management lever.', 'Governance is visibly in place.', 'Outcome accountability routines', 'More predictable execution and better prioritization.', 'executive'),
    ('manage_decision_making', 1, 'Define one simple customer decision forum with a fixed review cadence.', 'urgent_foundation', 'Make decisions visible.', 'Decisions are mostly internal.', 'Decision forum; fixed cadence', 'Earlier issue detection and better prioritization.', 'direct'),
    ('manage_decision_making', 2, 'Link customer decisions to named owners, actions, and follow-up checks.', 'build_consistency', 'Close the gap between insight and action.', 'Customer evidence influences some decisions.', 'Named owners; follow-up checks', 'More reliable execution and fewer repeated issues.', 'balanced'),
    ('manage_decision_making', 3, 'Use structured customer decisions to guide planning and resource choices.', 'scale_advantage', 'Make customer evidence a management input.', 'Customer evidence systematically shapes decisions.', 'Planning and resource alignment', 'Stronger decision quality and business alignment.', 'executive'),
    ('analyze_feedback_collection', 1, 'Set one recurring feedback pulse and one weekly review routine.', 'urgent_foundation', 'Start with a simple logging rhythm.', 'Feedback is collected inconsistently.', 'Weekly review routine; one logging point', 'Earlier issue detection and better visibility.', 'direct'),
    ('analyze_feedback_collection', 2, 'Expand feedback collection across the main journeys and review it cross-functionally.', 'build_consistency', 'Broaden the capture process.', 'Some channels or tools exist, but coverage is partial.', 'Journey coverage expansion; cross-functional review', 'Better visibility across the full customer journey.', 'balanced'),
    ('analyze_feedback_collection', 3, 'Embed customer feedback reviews into regular service and decision routines.', 'scale_advantage', 'Make listening part of operations.', 'Feedback is captured across key touchpoints.', 'Embedded feedback governance', 'Stronger decision quality and less blind-spot risk.', 'executive'),
    ('analyze_use_of_insights', 1, 'Pick a small set of CX measures and review them on a fixed cadence.', 'urgent_foundation', 'Start with a small set of signals.', 'Feedback is observed informally.', 'Fixed-cadence insight review', 'Better focus on the most important issues.', 'direct'),
    ('analyze_use_of_insights', 2, 'Link CX measures to owners and follow-up actions when scores move.', 'build_consistency', 'Connect review to action.', 'Some theme review or prioritization exists.', 'Owners and follow-up actions', 'More reliable response to insight shifts.', 'balanced'),
    ('analyze_use_of_insights', 3, 'Use CX measures in a broader dashboard that steers priorities and decisions.', 'scale_advantage', 'Make insight operational.', 'Feedback is translated into actionable insight.', 'Executive dashboard', 'Stronger prioritization and better investment focus.', 'executive'),
    ('analyze_channel_consistency', 1, 'Define one shared cross-channel service standard for the main customer touchpoints.', 'urgent_foundation', 'Establish one common standard.', 'Channels operate separately.', 'Shared channel standard', 'Fewer inconsistent customer experiences.', 'direct'),
    ('analyze_channel_consistency', 2, 'Review channel handoffs regularly and fix the biggest consistency gaps first.', 'build_consistency', 'Fix the highest-friction handoffs.', 'Some shared standards or handoffs exist.', 'Handoff review routine', 'Lower rework and better continuity.', 'balanced'),
    ('analyze_channel_consistency', 3, 'Use cross-channel standards to steer a more coherent end-to-end experience.', 'scale_advantage', 'Turn consistency into an operating discipline.', 'Channels are managed with shared context.', 'Cross-channel governance', 'More coherent journeys and better trust.', 'executive'),
    ('analyze_journey_visibility', 1, 'Document the top journeys and assign one owner to each.', 'urgent_foundation', 'Start where customer impact is highest.', 'Journey visibility is weak or absent.', 'Priority journey ownership', 'Better focus on the highest-friction experiences.', 'direct'),
    ('analyze_journey_visibility', 2, 'Review key journeys on a fixed cadence and log the main friction points.', 'build_consistency', 'Make journeys a living management tool.', 'Some journeys are mapped or discussed.', 'Journey review cadence; friction log', 'Stronger cross-team alignment and prioritization.', 'balanced'),
    ('analyze_journey_visibility', 3, 'Use owned journeys as the backbone for planning and service decisions.', 'scale_advantage', 'Scale journey management into the operating model.', 'Key journeys are owned and reviewed cross-functionally.', 'Journey operating model', 'Better investment focus and end-to-end experience quality.', 'executive'),
    ('improve_measurement_continuous_improvement', 1, 'Create one shared improvement backlog with owner, due date, and status.', 'urgent_foundation', 'Create one clear improvement system.', 'Measures are limited or disconnected from action.', 'Shared backlog; owner; due date', 'Higher completion discipline and clearer ownership.', 'direct'),
    ('improve_measurement_continuous_improvement', 2, 'Run a regular improvement review to reprioritize actions and verify progress.', 'build_consistency', 'Make follow-through reliable.', 'Measures are tracked and reviewed.', 'Improvement review cadence', 'More reliable execution and measurable outcomes.', 'balanced'),
    ('improve_measurement_continuous_improvement', 3, 'Manage improvement work as a portfolio by customer and business impact.', 'scale_advantage', 'Turn improvement into a managed portfolio.', 'Measures are tied to targets and outcomes.', 'Impact-based improvement portfolio', 'Better resource allocation and stronger value delivery.', 'executive'),
    ('improve_acting_on_pain_points', 1, 'Introduce one simple root-cause check before closing recurring pain points.', 'urgent_foundation', 'Stop closing issues too early.', 'Pain points are handled reactively.', 'Root-cause check before closure', 'Fewer recurring complaints and lower service waste.', 'direct'),
    ('improve_acting_on_pain_points', 2, 'Run recurring pain-point reviews and connect findings to action plans.', 'build_consistency', 'Strengthen prioritization and follow-through.', 'Some backlog or owner process exists.', 'Recurring pain-point review', 'More reliable remediation and better learning.', 'balanced'),
    ('improve_acting_on_pain_points', 3, 'Combine pain-point reviews with trend monitoring to catch issues earlier.', 'scale_advantage', 'Move from reactive to proactive.', 'Pain points are managed through a repeatable loop.', 'Trend monitoring and validation', 'Fewer failures and faster recovery.', 'executive')
)
INSERT INTO capability_recommendations (
  capability_id,
  maturity_level_id,
  recommendation_guideline,
  priority_hint,
  consultant_note,
  evidence_to_cite,
  initiative_suggestions,
  business_impact,
  tone_hint
)
SELECT
  c.id,
  ml.id,
  r.recommendation_guideline,
  r.priority_hint,
  r.consultant_note,
  r.evidence_to_cite,
  r.initiative_suggestions,
  r.business_impact,
  r.tone_hint
FROM recommendation_rows r
JOIN capabilities c ON c.code = r.code
JOIN maturity_levels ml ON ml.level_number = r.level_number
ON CONFLICT (capability_id, maturity_level_id)
DO UPDATE SET
  recommendation_guideline = EXCLUDED.recommendation_guideline,
  priority_hint = EXCLUDED.priority_hint,
  consultant_note = EXCLUDED.consultant_note,
  evidence_to_cite = EXCLUDED.evidence_to_cite,
  initiative_suggestions = EXCLUDED.initiative_suggestions,
  business_impact = EXCLUDED.business_impact,
  tone_hint = EXCLUDED.tone_hint;

COMMIT;
