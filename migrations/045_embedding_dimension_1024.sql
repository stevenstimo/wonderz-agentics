-- Migration 045: BGE-M3 embeddings (1024 dimensions)
-- Replaces OpenAI/Voyage (1536) with local BGE-M3. Existing rows cleared — retrain agents.

ALTER TABLE agent_knowledge DROP COLUMN IF EXISTS embedding;
ALTER TABLE agent_knowledge ADD COLUMN embedding vector(1024);

DROP INDEX IF EXISTS idx_agent_knowledge_embedding;
CREATE INDEX idx_agent_knowledge_embedding ON agent_knowledge
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
