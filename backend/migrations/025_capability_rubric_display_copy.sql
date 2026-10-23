BEGIN;

ALTER TABLE capability_maturity_rubrics
    ADD COLUMN IF NOT EXISTS card_summary TEXT,
    ADD COLUMN IF NOT EXISTS modal_summary TEXT;

COMMIT;
