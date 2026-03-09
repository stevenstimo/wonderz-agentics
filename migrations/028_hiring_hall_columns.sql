-- Migration: Hiring Hall — goal, category, is_active, is_suspended
-- Product Spec v1.1: goal = wat doet deze agent voor de crew; category = Management/Content/etc.
-- Voer handmatig uit of via migration runner.

ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS goal TEXT;

ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Custom';

ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN DEFAULT false;

ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS system_prompt TEXT;

-- Index voor snelle filtering
CREATE INDEX IF NOT EXISTS idx_hired_agents_role ON hired_agents(role);
CREATE INDEX IF NOT EXISTS idx_hired_agents_active ON hired_agents(is_active) WHERE is_active = true;
