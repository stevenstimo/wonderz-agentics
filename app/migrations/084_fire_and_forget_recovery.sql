-- Pattern: fire-and-forget / Aanpak A
-- Fase 1: ondersteuning voor stuck-recovery (worker/backend crash) op seo_jobs.
-- knowledge_documents en client_datasources hebben al updated_at.

ALTER TABLE seo_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

UPDATE seo_jobs
SET updated_at = COALESCE(completed_at, created_at, now())
WHERE updated_at IS NULL;
