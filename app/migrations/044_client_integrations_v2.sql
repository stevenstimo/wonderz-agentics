-- Per-client Google OAuth: tokens per user_id + client_slug
ALTER TABLE client_integrations
ADD COLUMN IF NOT EXISTS client_slug TEXT DEFAULT NULL;

DROP INDEX IF EXISTS client_integrations_user_id_integration_type_key;

ALTER TABLE client_integrations
DROP CONSTRAINT IF EXISTS client_integrations_user_id_integration_type_key;

ALTER TABLE client_integrations
DROP CONSTRAINT IF EXISTS client_integrations_user_type_key;

ALTER TABLE client_integrations
ADD CONSTRAINT client_integrations_user_client_type
UNIQUE(user_id, client_slug, integration_type);

CREATE INDEX IF NOT EXISTS idx_client_integrations_client_slug
ON client_integrations(client_slug);

