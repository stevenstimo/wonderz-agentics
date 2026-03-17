-- Allow logging system_events for any agent_id (e.g. copywriter, reviewer) without requiring a row in hired_agents.
-- Removes FK so INSERT no longer fails when agent_id is a role name not present in hired_agents.
ALTER TABLE system_events DROP CONSTRAINT IF EXISTS system_events_agent_id_fkey;
