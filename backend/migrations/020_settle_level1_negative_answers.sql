BEGIN;

-- Update whichever evidence column exists in this deployment. The current app
-- model uses evidence_required, while some environments expose expected_evidence.
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
            'manage_decision_making',
            'customer feedback example, decision note, leadership meeting minutes, prioritization record, roadmap change, policy update, budget decision, customer complaint summary',
            'Goal: Identify if customer evidence impacts decisions. Start by asking for one recent example. If the user says "pass" or "don''t know", accept this as evidence of a reactive/internal culture and move on. DO NOT ask multiple questions.'
          ),
          (
            'analyze_feedback_collection',
            'email inbox, Excel tracker, survey export, complaint log, call notes, shared mailbox owner, feedback tag, weekly review note, CRM case list',
            'Goal: Map feedback channels. If the user gives a simple answer like "email", acknowledge it and ask who manages those emails. Do not repeat the channel question. DO NOT ask multiple questions.'
          ),
          (
            'manage_cx_culture',
            'team ritual agenda, manager coaching note, CX playbook, service standard, recognition record, training attendance, QA scorecard, customer story shared in meeting',
            'Goal: Understand whether customer-focused behaviour is reinforced in daily work. Ask for one recent example of coaching, recognition, or a team routine. If the user says "pass" or "don''t know", accept this as evidence that CX culture is informal and move on. DO NOT ask multiple questions.'
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
      'manage_decision_making',
      1,
      'Level 1 / Basic Reactive: Decisions are internal, reactive, or cost-led. No formal process connects customer feedback to decisions. The user cannot provide a specific example of customer evidence changing a plan, says "I don''t know", says "pass", or confirms decisions depend on individual judgement.'
    ),
    (
      'manage_decision_making',
      2,
      'Level 2 / Established: Customer feedback influences some decisions, but the practice is partial, siloed, or inconsistent. Some examples exist, yet ownership, cadence, and decision records are not systematic across teams.'
    ),
    (
      'manage_decision_making',
      3,
      'Level 3 / Advanced: Customer evidence is systematically used in decision-making through clear governance, named owners, recurring reviews, documented trade-offs, and visible changes to priorities, policies, products, or service design.'
    ),
    (
      'analyze_feedback_collection',
      1,
      'Level 1 / Basic Reactive: Feedback collection is informal, ad hoc, or limited to a single basic channel such as email only, phone notes, or complaints. No formal tool, structured tagging, dedicated owner, or regular analysis is in place.'
    ),
    (
      'analyze_feedback_collection',
      2,
      'Level 2 / Established: Feedback is collected through some defined channels or basic tools such as surveys, email, Excel, CRM cases, or complaint logs, but coverage, ownership, tagging, and review cadence are inconsistent.'
    ),
    (
      'analyze_feedback_collection',
      3,
      'Level 3 / Advanced: Feedback is collected across key touchpoints through structured channels with clear ownership, taxonomy or tagging, regular review cadence, integrated tools, and links to action or insight routines.'
    ),
    (
      'manage_cx_culture',
      1,
      'Level 1 / Basic Reactive: No formal CX culture process exists. Customer-focused behaviours are ad hoc, reactive, or depend on individual goodwill, manager preference, or isolated frontline effort. The user may say "I don''t know", "pass", or provide no example of reinforcement.'
    ),
    (
      'manage_cx_culture',
      2,
      'Level 2 / Established: Some CX behaviours are encouraged through training, coaching, team routines, or service standards, but adoption is uneven by team, channel, or manager and is not consistently linked to outcomes.'
    ),
    (
      'manage_cx_culture',
      3,
      'Level 3 / Advanced: CX culture is actively led and reinforced through leadership routines, coaching, recognition, practical standards, quality feedback, and cross-functional behaviours tied to customer outcomes.'
    )
)
UPDATE capability_maturity_rubrics r
SET
  description = u.description,
  updated_at = NOW()
FROM rubric_updates u
JOIN capabilities c ON c.code = u.code
JOIN maturity_levels ml ON ml.level_number = u.level_number
WHERE r.capability_id = c.id
  AND r.maturity_level_id = ml.id;

COMMIT;
