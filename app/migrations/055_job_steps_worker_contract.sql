-- Platform Spec V1: worker output + validation status on job_steps
ALTER TABLE job_steps
  ADD COLUMN IF NOT EXISTS worker_output JSONB,
  ADD COLUMN IF NOT EXISTS validation_status TEXT DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS validation_warnings TEXT[];

ALTER TABLE job_steps DROP CONSTRAINT IF EXISTS chk_job_steps_validation_status;
ALTER TABLE job_steps ADD CONSTRAINT chk_job_steps_validation_status
  CHECK (validation_status IS NULL OR validation_status IN ('valid', 'invalid', 'pending'));
