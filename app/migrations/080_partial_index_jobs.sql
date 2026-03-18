-- INSTRUCTIE: Draai dit bestand NIET via een migration runner die BEGIN/COMMIT wrappers toevoegt.
-- CREATE INDEX CONCURRENTLY kan niet binnen een transaction block.
-- Draai via: psql -d <db> -f 080_partial_index_jobs.sql
-- Of plak direct in Supabase SQL editor (geen transaction wrapper).
-- Bij failure: DROP INDEX IF EXISTS idx_naam; en opnieuw aanmaken.

-- Partial index: alleen actieve job statussen
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_active
    ON jobs(status)
    WHERE status NOT IN ('completed', 'cancelled', 'failed');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_runs_job_id
    ON agent_runs(job_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_runs_created
    ON agent_runs(created_at DESC);
