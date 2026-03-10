-- User-scoped API integrations (API keys, credentials per user)
-- user_id from auth; integration_type: anthropic, openai, gemini, etc.
CREATE TABLE IF NOT EXISTS client_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    integration_type TEXT NOT NULL,
    api_key_encrypted TEXT,
    extra_config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, integration_type)
);

CREATE INDEX IF NOT EXISTS idx_client_integrations_user ON client_integrations(user_id);
