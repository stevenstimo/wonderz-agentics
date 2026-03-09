-- Client Layer & Platform Integrations (CREW INTELLIGENT Spec v1.0)
-- Run: psql "$DATABASE_URL" -f app/migrations/036_clients_layer.sql
-- Requires: jobs table, pgvector, pgcrypto

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 4.1 clients table
CREATE TABLE IF NOT EXISTS clients (
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

CREATE INDEX IF NOT EXISTS idx_clients_user ON clients(user_id);
CREATE INDEX IF NOT EXISTS idx_clients_slug ON clients(slug);

-- 4.2 client_integrations table
-- credentials: BYTEA for pgp_sym_encrypt output (encrypted at rest)
CREATE TABLE IF NOT EXISTS client_integrations (
  integration_id  TEXT PRIMARY KEY,
  client_id       TEXT NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
  platform        TEXT NOT NULL,
  credentials     BYTEA,
  config          JSONB NOT NULL DEFAULT '{}',
  status          TEXT CHECK (status IN ('connected', 'expired', 'error', 'disconnected')) DEFAULT 'connected',
  last_synced_at  TIMESTAMPTZ,
  connected_at    TIMESTAMPTZ DEFAULT now(),
  error_message   TEXT,
  UNIQUE(client_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_integrations_client ON client_integrations(client_id);
CREATE INDEX IF NOT EXISTS idx_integrations_platform ON client_integrations(platform);
CREATE INDEX IF NOT EXISTS idx_integrations_status ON client_integrations(status);

-- 4.3 client_knowledge table
CREATE TABLE IF NOT EXISTS client_knowledge (
  knowledge_id BIGSERIAL PRIMARY KEY,
  client_id    TEXT NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
  source_type  TEXT CHECK (source_type IN ('url', 'file', 'manual')),
  source_ref   TEXT NOT NULL,
  chunk_text   TEXT NOT NULL,
  embedding    vector(1536),
  chunk_index  INTEGER,
  is_active    BOOLEAN DEFAULT true,
  added_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_client_knowledge_client ON client_knowledge(client_id);
CREATE INDEX IF NOT EXISTS idx_client_knowledge_embedding ON client_knowledge
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 4.4 ALTER TABLE jobs
ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS client_id TEXT REFERENCES clients(client_id),
  ADD COLUMN IF NOT EXISTS client_mention TEXT;

CREATE INDEX IF NOT EXISTS idx_jobs_client ON jobs(client_id);
