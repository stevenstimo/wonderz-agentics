-- Skills library
CREATE TABLE IF NOT EXISTS agent_skills (
    skill_id TEXT PRIMARY KEY,              -- skill:copywriting:seo
    name TEXT NOT NULL,                     -- "SEO Copywriting"
    domain TEXT NOT NULL,                   -- copywriting, seo, content-writing
    skill_type TEXT NOT NULL CHECK (skill_type IN ('technique', 'checklist', 'voice', 'anti-patterns')),
    content TEXT NOT NULL,                  -- De skill instructies (Markdown)
    version INTEGER DEFAULT 1,
    applicable_to TEXT[] DEFAULT '{}',      -- Welke agent roles kunnen deze skill gebruiken
    success_rate DECIMAL(3,2) DEFAULT 0.50, -- Start op 50%, evolueert
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent → Skill assignments
CREATE TABLE IF NOT EXISTS agent_skill_assignments (
    assignment_id BIGSERIAL PRIMARY KEY,
    agent_id TEXT REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
    skill_id TEXT REFERENCES agent_skills(skill_id) ON DELETE CASCADE,
    proficiency TEXT CHECK (proficiency IN ('learning', 'competent', 'expert')) DEFAULT 'competent',
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_id, skill_id)
);

-- Skill usage tracking
CREATE TABLE IF NOT EXISTS skill_usage_log (
    log_id BIGSERIAL PRIMARY KEY,
    job_id TEXT,
    agent_id TEXT,
    skill_id TEXT REFERENCES agent_skills(skill_id),
    was_successful BOOLEAN,
    feedback TEXT,
    logged_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_skills_domain ON agent_skills(domain);
CREATE INDEX IF NOT EXISTS idx_skills_applicable ON agent_skills USING GIN(applicable_to);
CREATE INDEX IF NOT EXISTS idx_skill_assignments_agent ON agent_skill_assignments(agent_id);
CREATE INDEX IF NOT EXISTS idx_skill_assignments_skill ON agent_skill_assignments(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_usage_skill ON skill_usage_log(skill_id);
