-- Fase C Feature 1: Job templates

CREATE TABLE IF NOT EXISTS job_templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    platform TEXT,
    job_post_template TEXT NOT NULL,
    required_agents JSONB,
    suggested_skills JSONB,
    estimated_duration_min INTEGER,
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_templates_category ON job_templates(category);
CREATE INDEX IF NOT EXISTS idx_templates_platform ON job_templates(platform);

-- Seed common templates
INSERT INTO job_templates (
    template_id, name, description, category, platform,
    job_post_template, required_agents, suggested_skills,
    estimated_duration_min
) VALUES (
    'template:seo-product-desc',
    'SEO-Optimized Product Description',
    'Generate search-friendly product descriptions with keywords',
    'marketing',
    'shopify',
    'Write a 300-word SEO-optimized product description for: [PRODUCT_NAME]. Include keywords: [KEYWORDS]. Target audience: [AUDIENCE]. Highlight: [KEY_FEATURES].',
    '["copywriter", "seo"]'::jsonb,
    '["seo-copywriting", "product-knowledge"]'::jsonb,
    15
) ON CONFLICT (template_id) DO NOTHING;

INSERT INTO job_templates (
    template_id, name, description, category, platform,
    job_post_template, required_agents, suggested_skills,
    estimated_duration_min
) VALUES (
    'template:social-announcement',
    'Product Launch Social Media Posts',
    'Create social media content for product launches',
    'marketing',
    'custom',
    'Create 3 social media posts (Twitter, LinkedIn, Instagram) announcing: [PRODUCT_NAME]. Tone: [TONE]. Include call-to-action: [CTA].',
    '["copywriter", "social-media-manager"]'::jsonb,
    '["social-media-writing", "brand-voice"]'::jsonb,
    10
) ON CONFLICT (template_id) DO NOTHING;

INSERT INTO job_templates (
    template_id, name, description, category, platform,
    job_post_template, required_agents, suggested_skills,
    estimated_duration_min
) VALUES (
    'template:support-response',
    'Customer Support Email Response',
    'Draft professional support responses',
    'support',
    'custom',
    'Draft a professional response to this customer inquiry: [INQUIRY]. Issue type: [ISSUE_TYPE]. Resolution: [RESOLUTION]. Tone: empathetic and helpful.',
    '["support-specialist"]'::jsonb,
    '["customer-service", "tone-matching"]'::jsonb,
    5
) ON CONFLICT (template_id) DO NOTHING;
