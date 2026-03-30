-- SEO jobs: validator score na generate_excel (ARQ worker).
-- Run: psql "$DATABASE_URL" -f app/migrations/091_seo_jobs_validation_score.sql

ALTER TABLE seo_jobs
ADD COLUMN IF NOT EXISTS validation_score INTEGER DEFAULT NULL;
