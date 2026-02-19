-- Token budget tracking for cost control
-- Applied: 2026-02-19

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS token_budget INTEGER DEFAULT 50000;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS token_limit_exceeded_at TIMESTAMPTZ;

ALTER TABLE job_steps ADD COLUMN IF NOT EXISTS token_limit_per_step INTEGER DEFAULT 10000;

CREATE INDEX IF NOT EXISTS idx_jobs_token_usage ON jobs(tokens_used, token_budget);
