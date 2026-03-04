-- Maak 3 nieuwe agents met skill-based approach
INSERT INTO hired_agents (agent_id, name, role, specialization, status, performance_score, completed_tasks, hired_at, tool_access_whitelist, system_instructions)
VALUES
  (
    'agent:copywriter:skilled-001',
    'Max - Senior Copywriter (Skills-Enhanced)',
    'copywriter',
    'copywriter',
    'active',
    0.80,
    0,
    NOW(),
    '["write_copy", "read_product", "read_analytics"]'::jsonb,
    'You are Max, a senior copywriter. You specialize in creating engaging, high-converting content.

Your approach:
- Always consider the target audience and platform
- Use data-driven language for B2B, conversational tone for B2C
- Follow SEO best practices when writing for web
- Structure content for scannability and readability

You have access to domain-specific skills that will be loaded before each task. Use them.'
  ),
  (
    'agent:reviewer:skilled-001',
    'Lisa - Content Reviewer (Skills-Enhanced)',
    'reviewer',
    'reviewer',
    'active',
    0.85,
    0,
    NOW(),
    '["review_content", "provide_feedback"]'::jsonb,
    'You are Lisa, a meticulous content reviewer. Your job is to ensure quality before publication.

You check for:
- Relevance to the brief
- Grammar and spelling
- Tone consistency
- Structure and readability
- Anti-patterns and common mistakes

You have access to anti-pattern skills. Use them to catch issues.'
  ),
  (
    'agent:seo:skilled-001',
    'Emma - SEO Specialist (Skills-Enhanced)',
    'seo',
    'seo',
    'active',
    0.75,
    0,
    NOW(),
    '["optimize_seo", "read_analytics", "keyword_research"]'::jsonb,
    'You are Emma, an SEO specialist. You optimize content for search engines while maintaining quality.

Your focus:
- Keyword placement and density
- Content structure (H1, H2, H3)
- Internal linking opportunities
- Meta descriptions and titles
- Readability and user intent

You have access to SEO best practice skills. Apply them rigorously.'
  )
ON CONFLICT (agent_id) DO NOTHING;

-- Assign skills to agents
-- Max (Copywriter) gets: SEO, both voice skills, structure, anti-patterns
INSERT INTO agent_skill_assignments (agent_id, skill_id, proficiency)
VALUES
  ('agent:copywriter:skilled-001', 'skill:copywriting:seo', 'expert'),
  ('agent:copywriter:skilled-001', 'skill:voice:b2b-professional', 'competent'),
  ('agent:copywriter:skilled-001', 'skill:voice:casual-conversational', 'competent'),
  ('agent:copywriter:skilled-001', 'skill:structure:content-hierarchy', 'expert'),
  ('agent:copywriter:skilled-001', 'skill:anti-patterns:common-mistakes', 'expert')
ON CONFLICT (agent_id, skill_id) DO NOTHING;

-- Lisa (Reviewer) gets: anti-patterns, structure
INSERT INTO agent_skill_assignments (agent_id, skill_id, proficiency)
VALUES
  ('agent:reviewer:skilled-001', 'skill:anti-patterns:common-mistakes', 'expert'),
  ('agent:reviewer:skilled-001', 'skill:structure:content-hierarchy', 'competent')
ON CONFLICT (agent_id, skill_id) DO NOTHING;

-- Emma (SEO) gets: SEO, structure
INSERT INTO agent_skill_assignments (agent_id, skill_id, proficiency)
VALUES
  ('agent:seo:skilled-001', 'skill:copywriting:seo', 'expert'),
  ('agent:seo:skilled-001', 'skill:structure:content-hierarchy', 'expert')
ON CONFLICT (agent_id, skill_id) DO NOTHING;
