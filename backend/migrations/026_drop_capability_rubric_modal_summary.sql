BEGIN;

ALTER TABLE capability_maturity_rubrics
    DROP COLUMN IF EXISTS modal_summary;

COMMIT;
