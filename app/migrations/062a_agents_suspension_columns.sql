-- Platform Spec V7: Add suspension columns to hired_agents if missing.
-- (agents table already has these in Supabase/V2; hired_agents may not.)

ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS suspension_reason TEXT;
