-- Fix schema drift: ensure validation_decisions has step_id (IF NOT EXISTS safe for existing 056 schema).
ALTER TABLE validation_decisions ADD COLUMN IF NOT EXISTS step_id UUID REFERENCES job_steps(id) ON DELETE SET NULL;
