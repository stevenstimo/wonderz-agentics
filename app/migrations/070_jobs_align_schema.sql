-- Align jobs table with production: finished_at, payload (JSONB)
-- Applied: 2026-03

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb;
