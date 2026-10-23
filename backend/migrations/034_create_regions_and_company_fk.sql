BEGIN;

CREATE TABLE IF NOT EXISTS regions (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE
);

ALTER TABLE regions
DROP COLUMN IF EXISTS code,
DROP COLUMN IF EXISTS latitude,
DROP COLUMN IF EXISTS longitude,
DROP COLUMN IF EXISTS sort_order,
DROP COLUMN IF EXISTS created_at,
DROP COLUMN IF EXISTS updated_at;

WITH region_rows(name) AS (
  VALUES
    ('Africa'),
    ('Antarctica'),
    ('Asia'),
    ('Europe'),
    ('North America'),
    ('Oceania'),
    ('South America')
)
INSERT INTO regions (name)
SELECT name
FROM region_rows
ON CONFLICT (name)
DO NOTHING;

ALTER TABLE companies
ADD COLUMN IF NOT EXISTS region_id BIGINT;

UPDATE companies c
SET region_id = r.id
FROM regions r
WHERE c.region_id IS NULL
  AND c.region IS NOT NULL
  AND (
    LOWER(BTRIM(c.region)) = LOWER(r.name)
    OR (LOWER(BTRIM(c.region)) IN ('middle east', 'asia-pacific', 'apac') AND r.name = 'Asia')
    OR (LOWER(BTRIM(c.region)) IN ('latin america') AND r.name = 'South America')
  );

CREATE INDEX IF NOT EXISTS ix_companies_region_id
  ON companies(region_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'companies_region_id_fkey'
  ) THEN
    ALTER TABLE companies
    ADD CONSTRAINT companies_region_id_fkey
    FOREIGN KEY (region_id) REFERENCES regions(id);
  END IF;
END $$;

COMMIT;
