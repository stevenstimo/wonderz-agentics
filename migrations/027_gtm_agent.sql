-- GTM Agent — Registreer de GTM (Growth, Marketing & Go-To-Market) specialist in hired_agents.
-- ASSUMPTION-BASED: Gebruikt het schema van agents.py (name, role, system_instructions, tool_access_whitelist, etc.)
-- Als de tabel het 007-schema heeft (agent_name, goal, tool_whitelist), voer dan handmatig een aangepaste INSERT uit.

-- Probeer insert met het uitgebreide schema (agents.py / Supabase migration)
INSERT INTO hired_agents (
    agent_id,
    name,
    role,
    specialization,
    status,
    system_instructions,
    tool_access_whitelist,
    knowledge_base_sources,
    hired_at,
    updated_at
) VALUES (
    'agent:gtm-specialist',
    'GTM Agent — Growth & Marketing Specialist',
    'gtm-specialist',
    'Growth Hacker, Content Creator, Trend Researcher, Feedback Synthesizer',
    'active',
    'GTM Agent die Growth Hacker + Content Creator + Trend Researcher + Feedback Synthesizer combineert. Cijfer-gedreven, platform-specifiek, viral-mechanic focused. Platforms: Wonderz, ClawAgency, Blogable.',
    '["read_analytics", "write_content", "read_market_data", "read_job_context"]'::jsonb,
    '[{"platform": "wonderz", "type": "config"}, {"platform": "clawagency", "type": "config"}, {"platform": "blogable", "type": "config"}]'::jsonb,
    NOW(),
    NOW()
)
ON CONFLICT (agent_id) DO UPDATE SET
    name = EXCLUDED.name,
    role = EXCLUDED.role,
    specialization = EXCLUDED.specialization,
    status = 'active',
    system_instructions = EXCLUDED.system_instructions,
    tool_access_whitelist = EXCLUDED.tool_access_whitelist,
    knowledge_base_sources = EXCLUDED.knowledge_base_sources,
    updated_at = NOW();
