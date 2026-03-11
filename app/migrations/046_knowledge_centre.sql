-- Migration 046: AI Agency Knowledge Centre — Fase 1
-- Spec: knowledge_centre_spec_v1_1.docx §11.2
-- Agency-wide: client_id IS NULL. Client-scoped: client_slug references clients.
-- ASSUMPTION-BASED: client_slug used (clients.slug) — spec says client_id; clients table uses slug as primary identifier in API.
-- ASSUMPTION-BASED: knowledge_permissions default 'read' for agents per user rule.

CREATE EXTENSION IF NOT EXISTS vector;

-- Document metadata (source URL/file, approval, scope)
CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url TEXT,
    source_type TEXT NOT NULL DEFAULT 'url' CHECK (source_type IN ('url', 'file')),
    title TEXT,
    client_slug TEXT,
    approved_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chunks with embeddings — agency-wide when document.client_slug IS NULL
-- Reuses BGE-M3 1024-dim from TrainingWorkflow
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES knowledge_documents(document_id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    embedding vector(1024),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document ON knowledge_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding ON knowledge_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_active ON knowledge_chunks(is_active) WHERE is_active = true;

-- Permissions: agents get default read. Spec: knowledge_permissions, agents standaard alleen read.
CREATE TABLE IF NOT EXISTS knowledge_permissions (
    permission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
    permission_level TEXT NOT NULL DEFAULT 'read' CHECK (permission_level IN ('read', 'write', 'admin')),
    client_slug TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(agent_id, client_slug)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_permissions_agent ON knowledge_permissions(agent_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_permissions_client ON knowledge_permissions(client_slug) WHERE client_slug IS NOT NULL;

-- Index for document lookup by scope
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_client ON knowledge_documents(client_slug) WHERE client_slug IS NOT NULL;
