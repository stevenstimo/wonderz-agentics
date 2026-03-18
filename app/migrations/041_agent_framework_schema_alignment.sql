-- app/migrations/041_agent_framework_schema_alignment.sql
-- Framework ref: docs/260317_crew_intelligent_agent_framework.md sectie 9
-- Optie A: nieuwe kolommen toevoegen, oude behouden

BEGIN;

-- tool_whitelist toevoegen (TEXT[]) + data kopiëren vanuit tool_access_whitelist (JSONB)
ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS tool_whitelist TEXT[] DEFAULT '{}';

UPDATE hired_agents
  SET tool_whitelist = CASE
    WHEN jsonb_typeof(tool_access_whitelist) = 'array' AND jsonb_array_length(tool_access_whitelist) > 0
    THEN ARRAY(SELECT jsonb_array_elements_text(tool_access_whitelist))
    ELSE '{}'
  END
  WHERE (tool_whitelist = '{}' OR tool_whitelist IS NULL)
    AND tool_access_whitelist IS NOT NULL;

-- knowledge_sources toevoegen (JSONB) + data kopiëren vanuit knowledge_base_sources
ALTER TABLE hired_agents
  ADD COLUMN IF NOT EXISTS knowledge_sources JSONB DEFAULT '[]';

UPDATE hired_agents
  SET knowledge_sources = COALESCE(knowledge_base_sources, '[]'::jsonb)
  WHERE (knowledge_sources = '[]'::jsonb OR knowledge_sources IS NULL)
    AND knowledge_base_sources IS NOT NULL;

-- Verificatie
SELECT column_name FROM information_schema.columns
WHERE table_name = 'hired_agents'
ORDER BY ordinal_position;

COMMIT;
