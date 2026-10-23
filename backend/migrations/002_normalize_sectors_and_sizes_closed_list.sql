BEGIN;

-- Closed lists:
-- - `sectors` and `company_sizes` are reference tables seeded by migration.
-- - The LLM can suggest labels with confidence, but suggestions are stored in *_detections tables
--   and must be mapped to an existing sector/size code.

-- 1) Reference tables (closed lists)
CREATE TABLE IF NOT EXISTS sectors (
  id          SERIAL PRIMARY KEY,
  code        TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS company_sizes (
  id          SERIAL PRIMARY KEY,
  code        TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2) Seed values (edit this section to match your exact closed taxonomy)
-- Sectors: minimal starter set + unknown. Replace/extend as needed.
INSERT INTO sectors (code, name) VALUES
  ('unknown', 'Unknown'),
  ('retail', 'Retail'),
  ('ecommerce', 'E-commerce'),
  ('banking', 'Banking'),
  ('insurance', 'Insurance'),
  ('telecom', 'Telecom'),
  ('healthcare', 'Healthcare'),
  ('travel', 'Travel & Hospitality'),
  ('saas', 'SaaS / Software'),
  ('manufacturing', 'Manufacturing'),
  ('logistics', 'Logistics'),
  ('public', 'Public Sector')
ON CONFLICT (code) DO NOTHING;

-- Company sizes: keep it coarse for MVP (closed set).
INSERT INTO company_sizes (code, name) VALUES
  ('unknown', 'Unknown'),
  ('micro', 'Micro (1-10)'),
  ('small', 'Small (11-50)'),
  ('medium', 'Medium (51-250)'),
  ('large', 'Large (251-1000)'),
  ('enterprise', 'Enterprise (1000+)')
ON CONFLICT (code) DO NOTHING;

-- 3) Add FK columns on companies (keep old text columns for now)
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS sector_id INTEGER,
  ADD COLUMN IF NOT EXISTS size_id INTEGER;

-- 4) Backfill: map existing free-text to known codes when possible, otherwise 'unknown'
-- Note: mapping is by normalized text == sector/code. If you previously stored "Retail", it maps to "retail".
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'companies' AND column_name = 'sector'
  ) THEN
    UPDATE companies c
    SET sector_id = s.id
    FROM sectors s
    WHERE c.sector IS NOT NULL
      AND trim(c.sector) <> ''
      AND s.code = lower(trim(c.sector));
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'companies' AND column_name = 'size'
  ) THEN
    UPDATE companies c
    SET size_id = cs.id
    FROM company_sizes cs
    WHERE c.size IS NOT NULL
      AND trim(c.size) <> ''
      AND cs.code = lower(trim(c.size));
  END IF;
END $$;

UPDATE companies
SET sector_id = (SELECT id FROM sectors WHERE code = 'unknown')
WHERE sector_id IS NULL;

UPDATE companies
SET size_id = (SELECT id FROM company_sizes WHERE code = 'unknown')
WHERE size_id IS NULL;

-- 5) Constraints + indexes
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_companies_sector') THEN
    ALTER TABLE companies
      ADD CONSTRAINT fk_companies_sector
      FOREIGN KEY (sector_id) REFERENCES sectors(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_companies_size') THEN
    ALTER TABLE companies
      ADD CONSTRAINT fk_companies_size
      FOREIGN KEY (size_id) REFERENCES company_sizes(id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_companies_sector_id ON companies(sector_id);
CREATE INDEX IF NOT EXISTS ix_companies_size_id ON companies(size_id);

ALTER TABLE companies
  ALTER COLUMN sector_id SET NOT NULL,
  ALTER COLUMN size_id SET NOT NULL;

-- 6) LLM detections (store raw label + confidence; can later be reviewed and mapped)
CREATE TABLE IF NOT EXISTS company_sector_detections (
  id              SERIAL PRIMARY KEY,
  company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  sector_id       INTEGER NULL REFERENCES sectors(id),
  raw_label       TEXT NOT NULL,
  confidence      DOUBLE PRECISION NOT NULL,
  source          TEXT NOT NULL DEFAULT 'llm',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_company_sector_detections_company_id
  ON company_sector_detections(company_id);

CREATE TABLE IF NOT EXISTS company_size_detections (
  id              SERIAL PRIMARY KEY,
  company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  size_id         INTEGER NULL REFERENCES company_sizes(id),
  raw_label       TEXT NOT NULL,
  confidence      DOUBLE PRECISION NOT NULL,
  source          TEXT NOT NULL DEFAULT 'llm',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_company_size_detections_company_id
  ON company_size_detections(company_id);

COMMIT;
