-- Fix schema drift: ensure knowledge_usage_log has job_id and step_id (IF NOT EXISTS safe for existing 053 schema).
ALTER TABLE knowledge_usage_log ADD COLUMN IF NOT EXISTS job_id UUID REFERENCES jobs(id) ON DELETE CASCADE;
ALTER TABLE knowledge_usage_log ADD COLUMN IF NOT EXISTS step_id UUID REFERENCES job_steps(id) ON DELETE SET NULL;
