-- Migration 047: Knowledge Centre fix — spec §3.1, §3.3, §3.4
-- Corrects 046: adds missing columns, creates knowledge_versions, fixes knowledge_permissions.

-- 1. knowledge_documents: add doc_id (for supersedes self-FK and permissions FK)
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS doc_id TEXT;
UPDATE knowledge_documents SET doc_id = 'doc_' || replace(document_id::text, '-', '') WHERE doc_id IS NULL;
ALTER TABLE knowledge_documents ALTER COLUMN doc_id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_documents_doc_id ON knowledge_documents(doc_id);

-- 2. knowledge_documents: add §3.1 columns
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS doc_type TEXT DEFAULT 'sop';
UPDATE knowledge_documents SET doc_type = 'sop' WHERE doc_type IS NULL;
ALTER TABLE knowledge_documents DROP CONSTRAINT IF EXISTS knowledge_documents_doc_type_check;
ALTER TABLE knowledge_documents ADD CONSTRAINT knowledge_documents_doc_type_check
  CHECK (doc_type IN ('playbook','sop','framework','template','case_study','policy','research','client_context','skill_spec'));
ALTER TABLE knowledge_documents ALTER COLUMN doc_type SET NOT NULL;

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS domain TEXT DEFAULT 'general';
UPDATE knowledge_documents SET domain = 'general' WHERE domain IS NULL;
ALTER TABLE knowledge_documents ALTER COLUMN domain SET NOT NULL;

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS function_tag TEXT DEFAULT 'general';
UPDATE knowledge_documents SET function_tag = 'general' WHERE function_tag IS NULL;
ALTER TABLE knowledge_documents ALTER COLUMN function_tag SET NOT NULL;

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS owner TEXT;
UPDATE knowledge_documents SET owner = COALESCE(approved_by, 'system') WHERE owner IS NULL;
ALTER TABLE knowledge_documents ALTER COLUMN owner SET NOT NULL;

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft';
ALTER TABLE knowledge_documents DROP CONSTRAINT IF EXISTS knowledge_documents_status_check;
ALTER TABLE knowledge_documents ADD CONSTRAINT knowledge_documents_status_check
  CHECK (status IN ('draft','approved','stale','archived'));

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS access_level TEXT DEFAULT 'reference';
ALTER TABLE knowledge_documents DROP CONSTRAINT IF EXISTS knowledge_documents_access_level_check;
ALTER TABLE knowledge_documents ADD CONSTRAINT knowledge_documents_access_level_check
  CHECK (access_level IN ('reference','approved','restricted'));

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT '{}';
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS input_for TEXT[] DEFAULT '{}';
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS output_type TEXT;
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS related_docs TEXT[] DEFAULT '{}';
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS supersedes TEXT;
ALTER TABLE knowledge_documents DROP CONSTRAINT IF EXISTS knowledge_documents_supersedes_fkey;
ALTER TABLE knowledge_documents ADD CONSTRAINT knowledge_documents_supersedes_fkey
  FOREIGN KEY (supersedes) REFERENCES knowledge_documents(doc_id);

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ DEFAULT now();
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS valid_until TIMESTAMPTZ;
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS last_reviewed TIMESTAMPTZ;
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS second_approver TEXT;
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS review_interval_days INTEGER DEFAULT 180;

-- 3. knowledge_versions (spec §3.3)
CREATE TABLE IF NOT EXISTS knowledge_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id TEXT NOT NULL REFERENCES knowledge_documents(doc_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL,
    UNIQUE(doc_id, version)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_versions_doc ON knowledge_versions(doc_id);

-- 4. knowledge_permissions: add doc_id, domain, role, granted_by, valid_until (spec §3.4)
ALTER TABLE knowledge_permissions ADD COLUMN IF NOT EXISTS doc_id TEXT;
ALTER TABLE knowledge_permissions ADD COLUMN IF NOT EXISTS domain TEXT;
ALTER TABLE knowledge_permissions ADD COLUMN IF NOT EXISTS role TEXT;
ALTER TABLE knowledge_permissions ADD COLUMN IF NOT EXISTS granted_by TEXT DEFAULT 'system';
UPDATE knowledge_permissions SET granted_by = 'system' WHERE granted_by IS NULL;
ALTER TABLE knowledge_permissions ALTER COLUMN granted_by SET NOT NULL;
ALTER TABLE knowledge_permissions ADD COLUMN IF NOT EXISTS valid_until TIMESTAMPTZ;

-- Add FK for doc_id (after doc_id exists in knowledge_documents)
ALTER TABLE knowledge_permissions DROP CONSTRAINT IF EXISTS knowledge_permissions_doc_id_fkey;
ALTER TABLE knowledge_permissions ADD CONSTRAINT knowledge_permissions_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES knowledge_documents(doc_id) ON DELETE CASCADE;

-- Drop old UNIQUE to allow doc-scoped permissions
ALTER TABLE knowledge_permissions DROP CONSTRAINT IF EXISTS knowledge_permissions_agent_id_client_slug_key;
