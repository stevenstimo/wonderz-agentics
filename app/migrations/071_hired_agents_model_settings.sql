-- hired_agents: model settings for HR / agent config UI
-- Applied: 2026-03

ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS model TEXT,
  ADD COLUMN IF NOT EXISTS temperature FLOAT DEFAULT 0.7,
  ADD COLUMN IF NOT EXISTS top_p FLOAT DEFAULT 0.9,
  ADD COLUMN IF NOT EXISTS max_tokens INTEGER DEFAULT 4000,
  ADD COLUMN IF NOT EXISTS agent_version TEXT;
