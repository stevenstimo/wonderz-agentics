-- Client Layer & Platform Integrations (CREW INTELLIGENT Spec v1.0)
-- Run: psql "$DATABASE_URL" -f app/migrations/036_clients_layer.sql
-- Requires: jobs table, pgvector, pgcrypto
--
-- NOTE: Uses agency_clients (not clients) to avoid conflict with existing
-- clients table (id UUID, different schema). jobs.agency_client_id for @mention.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 4.1 agency_clients table (spec: clients)
CREATE TABLE IF NOT EXISTS agency_clients (
  client_id   TEXT PRIMARY KEY,
  user_id     UUID NOT NULL,
  client_name TEXT NOT NULL,
  slug        TEXT NOT NULL,
  description TEXT,
  logo_url    TEXT,
  is_active   BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_agency_clients_user ON agency_clients(user_id);
CREATE INDEX IF NOT EXISTS idx_agency_clients_slug ON agency_clients(slug);

-- 4.2 agency_client_integrations (spec: client_integrations)
-- credentials: BYTEA for pgp_sym_encrypt output (encrypted at rest)
CREATE TABLE IF NOT EXISTS agency_client_integrations (
  integration_id  TEXT PRIMARY KEY,
  client_id       TEXT NOT NULL REFERENCES agency_clients(client_id) ON DELETE CASCADE,
  platform        TEXT NOT NULL,
  credentials     BYTEA,
  config          JSONB NOT NULL DEFAULT '{}',
  status          TEXT CHECK (status IN ('connected', 'expired', 'error', 'disconnected')) DEFAULT 'connected',
  last_synced_at  TIMESTAMPTZ,
  connected_at    TIMESTAMPTZ DEFAULT now(),
  error_message   TEXT,
  UNIQUE(client_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_agency_integrations_client ON agency_client_integrations(client_id);
CREATE INDEX IF NOT EXISTS idx_agency_integrations_platform ON agency_client_integrations(platform);
CREATE INDEX IF NOT EXISTS idx_agency_integrations_status ON agency_client_integrations(status);

-- 4.3 agency_client_knowledge (spec: client_knowledge)
CREATE TABLE IF NOT EXISTS agency_client_knowledge (
  knowledge_id BIGSERIAL PRIMARY KEY,
  client_id    TEXT NOT NULL REFERENCES agency_clients(client_id) ON DELETE CASCADE,
  source_type  TEXT CHECK (source_type IN ('url', 'file', 'manual')),
  source_ref   TEXT NOT NULL,
  chunk_text   TEXT NOT NULL,
  embedding    vector(1536),
  chunk_index  INTEGER,
  is_active    BOOLEAN DEFAULT true,
  added_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agency_knowledge_client ON agency_client_knowledge(client_id);
CREATE INDEX IF NOT EXISTS idx_agency_knowledge_embedding ON agency_client_knowledge
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 4.4 ALTER TABLE jobs: agency_client_id for @mention (spec: client_id)
-- Legacy jobs.client_id (UUID) stays for existing clients table
ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS agency_client_id TEXT REFERENCES agency_clients(client_id),
  ADD COLUMN IF NOT EXISTS client_mention TEXT;

CREATE INDEX IF NOT EXISTS idx_jobs_agency_client ON jobs(agency_client_id);
