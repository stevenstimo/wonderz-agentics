-- Migration 063: embedding_status for async embedding generation
-- Documents start as pending; background task sets processing → complete | failed.

ALTER TABLE knowledge_documents
  ADD COLUMN IF NOT EXISTS embedding_status TEXT DEFAULT 'pending';

ALTER TABLE knowledge_documents
  DROP CONSTRAINT IF EXISTS knowledge_documents_embedding_status_check;

ALTER TABLE knowledge_documents
  ADD CONSTRAINT knowledge_documents_embedding_status_check
  CHECK (embedding_status IN ('pending', 'processing', 'complete', 'failed'));

-- Existing rows: treat as complete (already embedded)
UPDATE knowledge_documents SET embedding_status = 'complete' WHERE embedding_status IS NULL;
