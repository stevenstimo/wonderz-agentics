-- Add scope column for Skill Factory filtering (agency_wide | client_specific | per_job)
ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT 'agency_wide';
UPDATE knowledge_documents SET scope = CASE WHEN client_slug IS NOT NULL THEN 'client_specific' ELSE 'agency_wide' END WHERE scope IS NULL OR scope = 'agency_wide';
ALTER TABLE knowledge_documents DROP CONSTRAINT IF EXISTS knowledge_documents_scope_check;
ALTER TABLE knowledge_documents ADD CONSTRAINT knowledge_documents_scope_check
  CHECK (scope IN ('agency_wide', 'client_specific', 'per_job'));
