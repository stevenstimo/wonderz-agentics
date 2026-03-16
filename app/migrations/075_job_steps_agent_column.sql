-- job_steps.agent: required in some envs for NOT NULL; align schema so INSERT can supply it.
ALTER TABLE job_steps ADD COLUMN IF NOT EXISTS agent TEXT;
