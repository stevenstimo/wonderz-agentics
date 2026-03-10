-- Migration 040: HR Manager columns (Product Spec v1.1 Sectie 6.2)
-- Run: psql "$DATABASE_URL" -f migrations/040_hr_manager_columns.sql
-- Or: source .venv && python3 -c "import asyncio; from app.db import init_db_pool; ..." (manual)

-- 1. job_steps: add agent_id, retry_count, retry_reason
ALTER TABLE job_steps ADD COLUMN IF NOT EXISTS agent_id TEXT;
ALTER TABLE job_steps ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE job_steps ADD COLUMN IF NOT EXISTS retry_reason TEXT;

-- 2. Backfill agent_id from agent_role via hired_agents
UPDATE job_steps js
SET agent_id = ha.agent_id
FROM hired_agents ha
WHERE js.agent_role = ha.role
  AND (js.agent_id IS NULL OR js.agent_id = '');

-- 3a. development_points: add root_cause (spec 6.2)
ALTER TABLE development_points
  ADD COLUMN IF NOT EXISTS root_cause TEXT;

-- 3b. training_requests: add approved_url, resolved_at (spec 6.2) — only if table exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'training_requests') THEN
    ALTER TABLE training_requests ADD COLUMN IF NOT EXISTS approved_url TEXT;
    ALTER TABLE training_requests ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
  END IF;
END $$;

-- Indexes for HR scan performance
CREATE INDEX IF NOT EXISTS idx_job_steps_agent_id ON job_steps(agent_id);
CREATE INDEX IF NOT EXISTS idx_job_steps_retry ON job_steps(retry_count) WHERE retry_count > 0;
CREATE INDEX IF NOT EXISTS idx_job_steps_started_at ON job_steps(started_at) WHERE started_at IS NOT NULL;
