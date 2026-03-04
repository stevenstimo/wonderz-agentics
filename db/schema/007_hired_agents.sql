-- Task 6: Agent lifecycle core tables
-- Assumption-based: agent identifiers are stable text keys like 'agent:seo'.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS hired_agents (
  agent_id TEXT PRIMARY KEY,
  agent_name TEXT NOT NULL,
  role TEXT NOT NULL,
  goal TEXT NOT NULL,
  system_prompt TEXT NOT NULL,
  tool_whitelist JSONB NOT NULL DEFAULT '[]'::jsonb,
  knowledge_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_knowledge (
  knowledge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  chunk_text TEXT NOT NULL,
  embedding VECTOR(1536),
  chunk_index INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Assumption-based: fixed list count is conservative for MVP and can be tuned per dataset size.
CREATE INDEX IF NOT EXISTS agent_knowledge_embedding_ivfflat_idx
ON agent_knowledge
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS hired_agents_is_active_idx ON hired_agents(is_active);
CREATE INDEX IF NOT EXISTS agent_knowledge_agent_id_idx ON agent_knowledge(agent_id);
