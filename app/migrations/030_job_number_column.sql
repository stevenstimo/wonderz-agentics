-- Migratie: job_number van JSONB naar echte kolom
-- Stap 1: kolom + sequence aanmaken
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_number_int INTEGER;
CREATE SEQUENCE IF NOT EXISTS jobs_job_number_seq START 1;

-- Stap 2: bestaande nummers backfillen vanuit context
UPDATE jobs 
SET job_number_int = (context->>'job_number')::INTEGER
WHERE context->>'job_number' IS NOT NULL
AND context->>'job_number' != '?'
AND context->>'job_number' ~ '^[0-9]+$';

-- Stap 3: sequence bijwerken naar hoogste bestaande nummer
SELECT setval('jobs_job_number_seq', COALESCE(MAX(job_number_int), 0) + 1)
FROM jobs;

-- Stap 4: default instellen
ALTER TABLE jobs ALTER COLUMN job_number_int SET DEFAULT nextval('jobs_job_number_seq');

-- Stap 5: NOT NULL na backfill (jobs zonder nummer krijgen een nieuw nummer)
UPDATE jobs SET job_number_int = nextval('jobs_job_number_seq') WHERE job_number_int IS NULL;
ALTER TABLE jobs ALTER COLUMN job_number_int SET NOT NULL;

-- Stap 6: index
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_job_number_int ON jobs(job_number_int);
