-- CEO deterministische skill-matching (260325_CURSOR_arq_activate_skills)
CREATE TABLE IF NOT EXISTS skill_registry (
    skill_id         TEXT PRIMARY KEY,
    skill_name       TEXT NOT NULL,
    description      TEXT NOT NULL,
    trigger_keywords TEXT[] NOT NULL DEFAULT '{}',
    agent_type       TEXT NOT NULL,
    tool_name        TEXT NOT NULL,
    input_schema     JSONB DEFAULT '{}',
    is_active        BOOLEAN DEFAULT true,
    priority         INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skill_registry_active
    ON skill_registry (is_active, priority DESC);

INSERT INTO skill_registry
    (skill_id, skill_name, description, trigger_keywords, agent_type, tool_name, priority)
VALUES
    ('seo-keyword-research', 'SEO Keyword Research',
     'Zoekwoordonderzoek en keyword planning via Google Search Console',
     ARRAY['seo', 'keyword', 'zoekwoord', 'zoekvolume', 'keyword research', 'organic'],
     'seo', 'keyword_research', 10),
    ('content-copywriting', 'Content Copywriting',
     'Schrijven van blogs, artikelen, productbeschrijvingen en andere content',
     ARRAY['schrijf', 'blog', 'artikel', 'tekst', 'content', 'copy', 'productbeschrijving'],
     'copywriter', 'write_copy', 10),
    ('data-analysis', 'Data Analyse',
     'Analyse van marketing data, GSC data, GA4 en campagne performance',
     ARRAY['analyse', 'data', 'rapport', 'statistieken', 'performance', 'resultaten', 'metrics'],
     'analyst', 'read_analytics', 8),
    ('paid-ads', 'Paid Advertising',
     'Google Ads en Meta Ads campagne strategie en uitvoering',
     ARRAY['ads', 'advertentie', 'campagne', 'google ads', 'meta ads', 'budget', 'roas'],
     'media_buyer', 'read_analytics', 9)
ON CONFLICT (skill_id) DO NOTHING;
