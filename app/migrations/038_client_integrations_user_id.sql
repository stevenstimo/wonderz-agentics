-- Patch: add user_id and integration columns to existing client_integrations
-- Table may have client_id; we add user_id for JWT-based auth

ALTER TABLE client_integrations
    ADD COLUMN IF NOT EXISTS user_id UUID,
    ADD COLUMN IF NOT EXISTS integration_type TEXT,
    ADD COLUMN IF NOT EXISTS api_key_encrypted TEXT,
    ADD COLUMN IF NOT EXISTS extra_config JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_client_integrations_user_id
    ON client_integrations(user_id);

-- Unique constraint for upsert (user_id + integration_type)
ALTER TABLE client_integrations
    DROP CONSTRAINT IF EXISTS client_integrations_user_type_key;
ALTER TABLE client_integrations
    ADD CONSTRAINT client_integrations_user_type_key UNIQUE (user_id, integration_type);

-- Allow user-scoped rows without client_id (legacy columns nullable for new path)
ALTER TABLE client_integrations
    ALTER COLUMN client_id DROP NOT NULL,
    ALTER COLUMN platform DROP NOT NULL;
