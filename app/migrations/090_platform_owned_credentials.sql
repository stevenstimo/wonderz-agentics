-- Platform-owned client credentials: owned_by + resolver-friendly indexes
-- Run: psql "$DATABASE_URL" -f app/migrations/090_platform_owned_credentials.sql

ALTER TABLE client_integrations
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT false;

ALTER TABLE client_integrations
  ADD COLUMN IF NOT EXISTS owned_by TEXT NOT NULL DEFAULT 'user',
  ADD COLUMN IF NOT EXISTS platform_client_id TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'client_integrations_owned_by_check'
  ) THEN
    ALTER TABLE client_integrations
      ADD CONSTRAINT client_integrations_owned_by_check
      CHECK (owned_by IN ('platform', 'user'));
  END IF;
END $$;

-- Backfill: treat OAuth-connected rows as active for lookup semantics
UPDATE client_integrations
SET is_active = true
WHERE COALESCE(is_active, false) = false
  AND client_slug IS NOT NULL
  AND TRIM(client_slug) <> ''
  AND (
    extra_config->>'oauth_connected' = 'true'
    OR extra_config ? 'refresh_token'
    OR (NULLIF(TRIM(COALESCE(api_key_encrypted, '')), '') IS NOT NULL)
  );

-- Promote existing client-scoped active connections to platform-owned
UPDATE client_integrations
SET owned_by = 'platform'
WHERE owned_by = 'user'
  AND client_slug IS NOT NULL
  AND TRIM(client_slug) <> ''
  AND COALESCE(is_active, false) = true;

CREATE INDEX IF NOT EXISTS idx_client_integrations_platform
  ON client_integrations(client_slug, integration_type, owned_by, is_active)
  WHERE owned_by = 'platform' AND COALESCE(is_active, false) = true;
