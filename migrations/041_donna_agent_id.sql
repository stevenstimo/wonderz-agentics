-- Migration: Donna agent_id wijzigen van agent:personal-assistant-6fa7 naar agent:personal-assistant:donna
-- Run: psql "$DATABASE_URL" -f migrations/041_donna_agent_id.sql

-- Stap 1: Kopieer Donna naar nieuwe agent_id (alle kolommen)
INSERT INTO hired_agents (
    agent_id, name, role, specialization, status, permissions,
    system_instructions, knowledge_base_sources, tool_access_whitelist,
    hiring_logic, performance_score, completed_tasks, hired_at, updated_at,
    is_suspended, system_prompt, goal, category, is_active
)
SELECT
    'agent:personal-assistant:donna',
    name, role, specialization, status, permissions,
    system_instructions, knowledge_base_sources, tool_access_whitelist,
    hiring_logic, performance_score, completed_tasks, hired_at, updated_at,
    is_suspended, system_prompt, goal, category, is_active
FROM hired_agents
WHERE agent_id = 'agent:personal-assistant-6fa7'
ON CONFLICT (agent_id) DO UPDATE SET
    name = EXCLUDED.name,
    role = EXCLUDED.role,
    tool_access_whitelist = EXCLUDED.tool_access_whitelist,
    system_prompt = EXCLUDED.system_prompt,
    goal = EXCLUDED.goal,
    updated_at = NOW();

-- Stap 2: Update eventuele child tables (indien van toepassing)
UPDATE agent_skill_assignments SET agent_id = 'agent:personal-assistant:donna'
WHERE agent_id = 'agent:personal-assistant-6fa7';

-- Stap 3: Verwijder oude Donna
DELETE FROM hired_agents WHERE agent_id = 'agent:personal-assistant-6fa7';
