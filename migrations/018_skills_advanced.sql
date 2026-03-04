-- Fase A Feature 1: Skill metrics

ALTER TABLE skill_usage_log
ADD COLUMN IF NOT EXISTS job_success BOOLEAN,
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER,
ADD COLUMN IF NOT EXISTS baseline_score FLOAT;

CREATE INDEX IF NOT EXISTS idx_skill_usage_job_success
ON skill_usage_log(skill_id, job_success);
