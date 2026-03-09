-- Rename agency_* tables to spec names (CREW INTELLIGENT Spec v1.0)
-- Run: psql "$DATABASE_URL" -f app/migrations/037_rename_agency_tables.sql
--
-- Handles conflict: existing clients table (id UUID) is renamed to clients_legacy.
-- jobs.client_id (UUID) is dropped; jobs.agency_client_id becomes jobs.client_id (TEXT).

-- 1. Rename existing clients to clients_legacy (frees "clients" name)
ALTER TABLE IF EXISTS clients RENAME TO clients_legacy;

-- 2. Drop FK and column for legacy jobs.client_id (UUID)
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_client_id_fkey;
ALTER TABLE jobs DROP COLUMN IF EXISTS client_id;

-- 3. Rename agency_* tables to spec names
ALTER TABLE agency_clients RENAME TO clients;
ALTER TABLE agency_client_integrations RENAME TO client_integrations;
ALTER TABLE agency_client_knowledge RENAME TO client_knowledge;

-- 4. Rename jobs.agency_client_id to jobs.client_id
ALTER TABLE jobs RENAME COLUMN agency_client_id TO client_id;

-- 5. Rename indexes for consistency
DROP INDEX IF EXISTS idx_jobs_agency_client;
CREATE INDEX IF NOT EXISTS idx_jobs_client ON jobs(client_id);

DROP INDEX IF EXISTS idx_agency_clients_user;
DROP INDEX IF EXISTS idx_agency_clients_slug;
CREATE INDEX IF NOT EXISTS idx_clients_user ON clients(user_id);
CREATE INDEX IF NOT EXISTS idx_clients_slug ON clients(slug);

DROP INDEX IF EXISTS idx_agency_integrations_client;
DROP INDEX IF EXISTS idx_agency_integrations_platform;
DROP INDEX IF EXISTS idx_agency_integrations_status;
CREATE INDEX IF NOT EXISTS idx_integrations_client ON client_integrations(client_id);
CREATE INDEX IF NOT EXISTS idx_integrations_platform ON client_integrations(platform);
CREATE INDEX IF NOT EXISTS idx_integrations_status ON client_integrations(status);

DROP INDEX IF EXISTS idx_agency_knowledge_client;
DROP INDEX IF EXISTS idx_agency_knowledge_embedding;
CREATE INDEX IF NOT EXISTS idx_client_knowledge_client ON client_knowledge(client_id);
CREATE INDEX IF NOT EXISTS idx_client_knowledge_embedding ON client_knowledge
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
