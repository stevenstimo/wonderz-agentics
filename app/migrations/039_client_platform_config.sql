-- Client-level platform configs: platform-specifieke IDs per client
-- client_slug verwijst naar clients.slug
-- Run: psql "$DATABASE_URL" -f app/migrations/039_client_platform_config.sql

CREATE TABLE IF NOT EXISTS client_platform_configs (
    config_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    client_slug TEXT NOT NULL,
    client_name TEXT NOT NULL,
    platform TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, client_slug, platform)
);

CREATE INDEX IF NOT EXISTS idx_client_platform_configs_user ON client_platform_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_client_platform_configs_slug ON client_platform_configs(client_slug);
