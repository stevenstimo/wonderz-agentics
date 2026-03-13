-- Add client_slug to seo_jobs for GSC-linked jobs (optional).
-- Run: psql "$DATABASE_URL" -f app/migrations/068_seo_jobs_client_slug.sql

ALTER TABLE seo_jobs
ADD COLUMN IF NOT EXISTS client_slug TEXT;
