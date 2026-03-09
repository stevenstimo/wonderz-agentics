-- Migration: Skills Master Tagging (lifecycle_stage, agent_role, use_case)
-- SKILLS LIBRARY — Master Tagging Update v1.0
-- Run: psql "$DATABASE_URL" -f migrations/030_skills_master_tags.sql

-- Add three tag columns for deterministic retrieval
ALTER TABLE agent_skills
ADD COLUMN IF NOT EXISTS lifecycle_stage TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS agent_role TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS use_case TEXT[] DEFAULT '{}';

-- Indexes for efficient filtering on /relevant endpoint
CREATE INDEX IF NOT EXISTS idx_skills_use_case ON agent_skills USING GIN(use_case);
CREATE INDEX IF NOT EXISTS idx_skills_agent_role ON agent_skills USING GIN(agent_role);
CREATE INDEX IF NOT EXISTS idx_skills_lifecycle_stage ON agent_skills USING GIN(lifecycle_stage);

-- Backfill: Explicit registry mappings (skill_id -> tags)
-- Skills built in this session (already correctly tagged in approve flow)
UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch','launch'], agent_role = ARRAY['gtm-strategist','project-lead'], use_case = ARRAY['market-entry','acquisition-planning']
WHERE skill_id = 'skill:gtm:strategy-commercial-v2';

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['paid-media-specialist','gtm-strategist'], use_case = ARRAY['paid-advertising','acquisition-planning']
WHERE skill_id = 'skill:gtm:paid-media-v1';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['compliance-reviewer','gtm-strategist'], use_case = ARRAY['compliance','market-entry']
WHERE skill_id = 'skill:gtm:ymyl-compliance-v1';

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['gtm-strategist','project-lead'], use_case = ARRAY['acquisition-planning','market-entry']
WHERE skill_id = 'skill:gtm:b2b2c-distribution-v1';

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['seo-specialist','gtm-strategist'], use_case = ARRAY['seo-optimization','market-entry']
WHERE skill_id = 'skill:seo:strategy-realistic-v2';

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale','retention'], agent_role = ARRAY['content-writer','gtm-strategist'], use_case = ARRAY['content-production','retention']
WHERE skill_id = 'skill:content:strategy-lifecycle-v2';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['gtm-strategist','market-analyst'], use_case = ARRAY['market-validation','market-entry']
WHERE skill_id = 'skill:gtm:market-sizing-tam-v1';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['gtm-strategist','brand-strategist'], use_case = ARRAY['competitive-differentiation','market-entry']
WHERE skill_id = 'skill:gtm:positioning-statement-v1';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch','launch'], agent_role = ARRAY['gtm-strategist'], use_case = ARRAY['acquisition-planning','market-entry']
WHERE skill_id = 'skill:gtm:channel-selection-entry-v1';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch','launch','scale'], agent_role = ARRAY['gtm-strategist','project-lead'], use_case = ARRAY['market-entry','acquisition-planning']
WHERE skill_id = 'skill:gtm:launch-sequencing-v1';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['compliance-reviewer','gtm-strategist'], use_case = ARRAY['compliance','market-entry']
WHERE skill_id = 'skill:gtm:regulatory-screening-v1';

-- Existing skills — explicit registry
UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['project-lead'], use_case = ARRAY['market-entry','market-validation']
WHERE skill_id = 'skill:ceo:intake';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch','launch'], agent_role = ARRAY['market-analyst'], use_case = ARRAY['market-validation','content-production']
WHERE skill_id = 'research-brief-synthesis';

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['seo-specialist'], use_case = ARRAY['seo-optimization']
WHERE skill_id = 'branded-vs-non-branded-keyword-strategy';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch','launch'], agent_role = ARRAY['seo-specialist'], use_case = ARRAY['seo-optimization']
WHERE skill_id = 'keyword-research-filtering-framework';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['seo-specialist','market-analyst'], use_case = ARRAY['competitive-differentiation','seo-optimization']
WHERE skill_id = 'competitive-keyword-gap-analysis';

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['paid-media-specialist'], use_case = ARRAY['paid-advertising']
WHERE skill_id = 'skill:google:rsa';

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['paid-media-specialist'], use_case = ARRAY['paid-advertising']
WHERE skill_id = 'skill:meta:ad-copy';

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['gtm-strategist','brand-strategist'], use_case = ARRAY['competitive-differentiation']
WHERE skill_id = 'competitive-differentiation-over-imitation' OR name ILIKE '%Competitive Differentiation Over Imitation%';

-- Default tags for remaining skills by domain (only where tags not yet set)
UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['gtm-strategist'], use_case = ARRAY['market-entry']
WHERE domain = 'strategy' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['paid-media-specialist'], use_case = ARRAY['paid-advertising']
WHERE domain = 'advertising' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['seo-specialist'], use_case = ARRAY['seo-optimization']
WHERE domain = 'seo' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['content-writer'], use_case = ARRAY['content-production']
WHERE domain IN ('content', 'copywriting') AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale','retention'], agent_role = ARRAY['content-writer'], use_case = ARRAY['retention']
WHERE domain = 'email' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch','scale'], agent_role = ARRAY['content-writer'], use_case = ARRAY['paid-advertising']
WHERE domain = 'social' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['brand-strategist'], use_case = ARRAY['competitive-differentiation']
WHERE domain = 'voice' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['audit'], agent_role = ARRAY['project-lead'], use_case = ARRAY['audit']
WHERE domain = 'quality' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['launch'], agent_role = ARRAY['content-writer'], use_case = ARRAY['content-production']
WHERE domain = 'structure' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['market-analyst'], use_case = ARRAY['market-validation']
WHERE domain = 'research' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');

UPDATE agent_skills SET lifecycle_stage = ARRAY['pre-launch'], agent_role = ARRAY['project-lead'], use_case = ARRAY['market-entry']
WHERE domain = 'management' AND (lifecycle_stage IS NULL OR lifecycle_stage = '{}');
