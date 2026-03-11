-- Migration 048: Knowledge Centre — FIX 1 (knowledge_versions audit) + FIX 2 (unify document_id)
-- Spec §3.3: change_note, approved_by, snapshot voor audit trail
-- Unify alle FKs op document_id (uuid) — drop doc_id

-- FIX 1: knowledge_versions audit trail kolommen
ALTER TABLE knowledge_versions ADD COLUMN IF NOT EXISTS change_note TEXT NOT NULL DEFAULT 'initial version';
ALTER TABLE knowledge_versions ADD COLUMN IF NOT EXISTS approved_by TEXT;
ALTER TABLE knowledge_versions ADD COLUMN IF NOT EXISTS snapshot JSONB NOT NULL DEFAULT '{}';

-- FIX 2: Unify op document_id — knowledge_versions
ALTER TABLE knowledge_versions DROP CONSTRAINT IF EXISTS knowledge_versions_doc_id_fkey;
ALTER TABLE knowledge_versions DROP CONSTRAINT IF EXISTS knowledge_versions_doc_id_version_key;

ALTER TABLE knowledge_versions ADD COLUMN IF NOT EXISTS document_id UUID;

UPDATE knowledge_versions kv
SET document_id = kd.document_id
FROM knowledge_documents kd
WHERE kd.doc_id = kv.doc_id;

ALTER TABLE knowledge_versions ALTER COLUMN document_id SET NOT NULL;
ALTER TABLE knowledge_versions DROP COLUMN IF EXISTS doc_id;

ALTER TABLE knowledge_versions ADD CONSTRAINT knowledge_versions_document_id_fkey
  FOREIGN KEY (document_id) REFERENCES knowledge_documents(document_id) ON DELETE CASCADE;
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_versions_doc_version
  ON knowledge_versions(document_id, version);
CREATE INDEX IF NOT EXISTS idx_knowledge_versions_document ON knowledge_versions(document_id);
DROP INDEX IF EXISTS idx_knowledge_versions_doc;

-- FIX 2: knowledge_permissions — doc_id → document_id
ALTER TABLE knowledge_permissions DROP CONSTRAINT IF EXISTS knowledge_permissions_doc_id_fkey;

ALTER TABLE knowledge_permissions ADD COLUMN IF NOT EXISTS document_id UUID;

UPDATE knowledge_permissions kp
SET document_id = kd.document_id
FROM knowledge_documents kd
WHERE kd.doc_id = kp.doc_id;

ALTER TABLE knowledge_permissions DROP COLUMN IF EXISTS doc_id;

ALTER TABLE knowledge_permissions ADD CONSTRAINT knowledge_permissions_document_id_fkey
  FOREIGN KEY (document_id) REFERENCES knowledge_documents(document_id) ON DELETE CASCADE;

-- FIX 2: knowledge_documents.supersedes — doc_id → document_id
ALTER TABLE knowledge_documents DROP CONSTRAINT IF EXISTS knowledge_documents_supersedes_fkey;

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS supersedes_document_id UUID;

UPDATE knowledge_documents kd
SET supersedes_document_id = kd2.document_id
FROM knowledge_documents kd2
WHERE kd.supersedes = kd2.doc_id;

ALTER TABLE knowledge_documents DROP COLUMN IF EXISTS supersedes;
ALTER TABLE knowledge_documents RENAME COLUMN supersedes_document_id TO supersedes;

ALTER TABLE knowledge_documents ADD CONSTRAINT knowledge_documents_supersedes_fkey
  FOREIGN KEY (supersedes) REFERENCES knowledge_documents(document_id);

-- FIX 2: knowledge_documents — drop doc_id
DROP INDEX IF EXISTS idx_knowledge_documents_doc_id;
ALTER TABLE knowledge_documents DROP COLUMN IF EXISTS doc_id;
