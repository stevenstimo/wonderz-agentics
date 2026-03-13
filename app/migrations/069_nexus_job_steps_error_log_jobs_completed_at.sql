-- NEXUS: queryable error log for job_steps, completed_at for jobs (reporting / HR Manager)
-- Applied: 2026-03

ALTER TABLE job_steps ADD COLUMN IF NOT EXISTS error_log TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

COMMENT ON COLUMN job_steps.error_log IS 'Technical failure message (timeout, API error); distinct from output JSON for analytics.';
COMMENT ON COLUMN jobs.completed_at IS 'Set when job status becomes COMPLETED (user approve-and-deploy).';
