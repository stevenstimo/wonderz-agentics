-- Skill Factory schema
-- Run: psql "$DATABASE_URL" -f app/migrations/082_skills.sql

CREATE TABLE IF NOT EXISTS skills (
  skill_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  description TEXT,
  trigger_condition TEXT,
  requires_tools TEXT[] DEFAULT '{}',
  requires_skills TEXT[] DEFAULT '{}',
  status TEXT DEFAULT 'active'
    CHECK (status IN ('active', 'inactive', 'draft')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);

-- Link skills to agents (hired_agents.skills is JSONB array of skill "name" strings).
-- This column is expected to exist from the Crew Intelligent framework schema,
-- but we add it defensively to make the migration idempotent.
ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_hired_agents_skills_gin
  ON hired_agents USING GIN (skills);

