BEGIN;

-- The application schema currently uses `evidence_required`; some deployments may
-- expose the same business field as `expected_evidence`. Update whichever exists.
DO $$
DECLARE
  evidence_column TEXT;
BEGIN
  SELECT column_name
  INTO evidence_column
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name = 'capabilities'
    AND column_name IN ('expected_evidence', 'evidence_required')
  ORDER BY CASE column_name WHEN 'expected_evidence' THEN 1 ELSE 2 END
  LIMIT 1;

  IF evidence_column IS NULL THEN
    RAISE NOTICE 'No expected_evidence/evidence_required column found on capabilities; skipping evidence update.';
  ELSE
    EXECUTE format($SQL$
      WITH capability_updates(code, expected_evidence, question_guidelines) AS (
        VALUES
          (
            'improve_acting_on_pain_points',
            'pain-point backlog, Jira ticket, Trello card, named owner, due date, action status, closure evidence, customer complaint log, post-fix validation note',
            'Goal: understand how the business acts on customer pain points. Ask for one recent pain point and what happened next. If vague, probe only on ownership or closure evidence. DO NOT ask multiple questions.'
          ),
          (
            'analyze_journey_visibility',
            'journey map, service blueprint, touchpoint inventory, journey owner, journey KPI dashboard, regular review deck, cross-functional workshop notes, pain-point register',
            'Goal: check visibility of the end-to-end customer journey. Ask for one key journey and how teams currently see or review it. If vague, probe only on the artifact or owner. DO NOT ask multiple questions.'
          ),
          (
            'manage_cx_culture',
            'CX playbook, service standards, coaching log, training attendance, recognition record, QA scorecard, team ritual agenda, customer story library, manager feedback note',
            'Goal: understand whether customer-focused behaviours are reinforced in daily work. Ask for one recent example of how a team was coached, guided, or recognized for customer impact. If vague, probe only on the routine or artifact used. DO NOT ask multiple questions.'
          )
      )
      UPDATE capabilities c
      SET
        %I = u.expected_evidence,
        question_guidelines = u.question_guidelines,
        updated_at = NOW()
      FROM capability_updates u
      WHERE c.code = u.code;
    $SQL$, evidence_column);
  END IF;
END $$;

WITH rubric_updates(code, level_number, description) AS (
  VALUES
    (
      'improve_acting_on_pain_points',
      1,
      'Basic / Reactive: No formal process for acting on customer pain points. Actions are ad hoc, reactive, or depend on individual goodwill. The team may respond only to complaints, with no shared backlog, owner, status tracking, or closure evidence.'
    ),
    (
      'improve_acting_on_pain_points',
      2,
      'Established: A pain-point process or backlog exists for some issues, but prioritization, ownership, tracking, or closure checks are inconsistent. Follow-up may work in certain teams but is not systematic across functions.'
    ),
    (
      'improve_acting_on_pain_points',
      3,
      'Advanced: Pain points are managed through a repeatable cross-functional improvement loop with clear prioritization, named owners, deadlines, status tracking, closure evidence, and validation that fixes improved the customer experience.'
    ),
    (
      'analyze_journey_visibility',
      1,
      'Basic / Reactive: No formal end-to-end journey visibility. Teams work from isolated touchpoints, individual knowledge, or complaints. There may be no journey map, service blueprint, journey owner, shared review, or tool showing the full customer path.'
    ),
    (
      'analyze_journey_visibility',
      2,
      'Established: Some journeys are mapped, discussed, or reviewed, but visibility is partial or siloed. Ownership, update cadence, pain-point tracking, and use in decision-making are not consistently applied.'
    ),
    (
      'analyze_journey_visibility',
      3,
      'Advanced: Key journeys are documented, owned, and reviewed cross-functionally. Journey visibility is used proactively to identify pain points, monitor outcomes, prioritize improvements, and guide business decisions.'
    ),
    (
      'manage_cx_culture',
      1,
      'Basic / Reactive: No formal CX culture routine or enablement process. Customer-focused behaviour is ad hoc, reactive, and depends on individual goodwill or manager preference. There may be no shared standards, coaching rhythm, recognition, or practical tools.'
    ),
    (
      'manage_cx_culture',
      2,
      'Established: Some CX training, coaching, rituals, or service standards exist, but adoption is partial or siloed. Reinforcement varies by team, manager, or channel and is not consistently linked to customer outcomes.'
    ),
    (
      'manage_cx_culture',
      3,
      'Advanced: CX culture is actively led and reinforced through cross-functional routines, coaching, recognition, practical standards, quality feedback, and leadership behaviours tied to customer outcomes.'
    )
)
INSERT INTO capability_maturity_rubrics (capability_id, maturity_level_id, description)
SELECT c.id, ml.id, r.description
FROM rubric_updates r
JOIN capabilities c ON c.code = r.code
JOIN maturity_levels ml ON ml.level_number = r.level_number
ON CONFLICT (capability_id, maturity_level_id)
DO UPDATE SET
  description = EXCLUDED.description,
  updated_at = NOW();

COMMIT;
