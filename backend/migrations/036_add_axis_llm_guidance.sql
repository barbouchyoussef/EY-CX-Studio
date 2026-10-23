BEGIN;

ALTER TABLE axes
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS question_guidelines TEXT;

UPDATE axes
SET
  description = 'Manage covers the organization mechanisms that make customer experience accountable: leadership attention, ownership, governance routines, decision rights, culture, and the way customer impact is reinforced in everyday management.',
  question_guidelines = 'Use this axis to understand how CX is owned and governed. Ask about accountability, recurring management routines, decision influence, leadership follow-up, team reinforcement, and whether customer issues have visible owners rather than informal handling.'
WHERE LOWER(code) = 'manage';

UPDATE axes
SET
  description = 'Analyze covers how the organization listens to customers and turns feedback into usable understanding: feedback capture, journey visibility, cross-channel consistency, pattern recognition, root-cause analysis, and prioritization of customer issues.',
  question_guidelines = 'Use this axis to understand how customer signals become insight. Ask about feedback sources, logging practices, journey views, handoffs across channels, theme review, root-cause work, and how teams decide which issues matter most.'
WHERE LOWER(code) = 'analyze';

UPDATE axes
SET
  description = 'Improve covers how the organization acts on customer pain points and measures improvement over time: execution discipline, action ownership, metric review, follow-through, validation of fixes, and continuous improvement loops.',
  question_guidelines = 'Use this axis to understand whether customer issues lead to measurable action. Ask about pain-point backlogs, owners, due dates, closure checks, CX metrics, review cadence, action triggers, validation, and learning loops.'
WHERE LOWER(code) = 'improve';

COMMIT;
