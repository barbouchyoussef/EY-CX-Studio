BEGIN;

-- ============================================================
-- 039: Seed maturity_levels and backfill capability_maturity_rubrics
-- ============================================================
-- The maturity_levels table was created in 000 but never populated.
-- All downstream migrations (017, 019, 020, etc.) that JOIN on
-- maturity_levels silently inserted 0 rows because the base table
-- was empty.  This migration fixes that.

-- 1) Seed the three standard maturity levels
INSERT INTO maturity_levels (level_number, label, description)
VALUES
  (1, 'Basic / Reactive',    'Initial, ad-hoc practices with limited structure or consistency.'),
  (2, 'Established',         'Defined practices with partial adoption and growing consistency.'),
  (3, 'Advanced / Proactive', 'Systematic, embedded practices with clear ownership and continuous improvement.')
ON CONFLICT (level_number) DO NOTHING;

-- 2) Re-run the rubric seed from migration 017 (originally produced 0 rows)
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

COMMIT;
