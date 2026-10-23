BEGIN;

-- Axes
INSERT INTO axes (code, name, sort_order)
VALUES
  ('manage', 'Manage', 1),
  ('analyze', 'Analyze', 2),
  ('improve', 'Improve', 3)
ON CONFLICT (code) DO NOTHING;

-- Capabilities (real code set)
INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'manage_cx_culture', 'CX culture', 10
FROM axes a WHERE a.code = 'manage'
ON CONFLICT (code) DO NOTHING;

INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'manage_ownership_governance', 'Ownership and governance', 20
FROM axes a WHERE a.code = 'manage'
ON CONFLICT (code) DO NOTHING;

INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'manage_decision_making', 'Decision-making', 30
FROM axes a WHERE a.code = 'manage'
ON CONFLICT (code) DO NOTHING;

INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'analyze_feedback_collection', 'Feedback collection', 10
FROM axes a WHERE a.code = 'analyze'
ON CONFLICT (code) DO NOTHING;

INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'analyze_use_of_insights', 'Use of insights', 20
FROM axes a WHERE a.code = 'analyze'
ON CONFLICT (code) DO NOTHING;

INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'analyze_channel_consistency', 'Channel consistency', 30
FROM axes a WHERE a.code = 'analyze'
ON CONFLICT (code) DO NOTHING;

INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'analyze_journey_visibility', 'Journey visibility', 40
FROM axes a WHERE a.code = 'analyze'
ON CONFLICT (code) DO NOTHING;

INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'improve_measurement_continuous_improvement', 'Measurement and continuous improvement', 10
FROM axes a WHERE a.code = 'improve'
ON CONFLICT (code) DO NOTHING;

INSERT INTO capabilities (axis_id, code, name, sort_order)
SELECT a.id, 'improve_acting_on_pain_points', 'Acting on pain points', 20
FROM axes a WHERE a.code = 'improve'
ON CONFLICT (code) DO NOTHING;

COMMIT;
