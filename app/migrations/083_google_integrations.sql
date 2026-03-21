-- Google integrations: client_integrations uitbreiding + platform registry
-- Zie docs/260320_CURSOR_google_integrations.md

ALTER TABLE client_integrations
  ADD COLUMN IF NOT EXISTS provider TEXT,
  ADD COLUMN IF NOT EXISTS scopes TEXT[],
  ADD COLUMN IF NOT EXISTS extra_data JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_client_integrations_provider
  ON client_integrations(user_id, client_slug, provider);

CREATE TABLE IF NOT EXISTS platform_integrations (
  id            BIGSERIAL PRIMARY KEY,
  provider      TEXT NOT NULL UNIQUE,
  is_enabled    BOOLEAN DEFAULT false,
  last_checked  TIMESTAMPTZ,
  error_message TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

INSERT INTO platform_integrations (provider, is_enabled) VALUES
  ('pagespeed', false),
  ('crux', false),
  ('natural_language', false),
  ('indexing', false),
  ('knowledge_graph', false),
  ('translate', false)
ON CONFLICT (provider) DO NOTHING;

INSERT INTO platform_integrations (provider, is_enabled) VALUES
  ('business_profile', false),
  ('youtube', false),
  ('merchant_center', false),
  ('sheets', false)
ON CONFLICT (provider) DO NOTHING;
