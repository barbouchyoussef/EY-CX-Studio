-- Add language column to assessments (default French)
ALTER TABLE assessments ADD COLUMN language VARCHAR(10) NOT NULL DEFAULT 'fr';
