-- Add embedding_status for async upload flow (pending → processing → complete/failed)
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS embedding_status TEXT DEFAULT 'pending';
