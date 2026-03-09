-- SEO Keyword Plan feature: seo_jobs + seo_keywords tables
-- Run: psql "$DATABASE_URL" -f app/migrations/034_seo_jobs.sql

CREATE TABLE IF NOT EXISTS seo_jobs (
  job_id TEXT PRIMARY KEY,
  brand_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  audience TEXT,
  language TEXT DEFAULT 'nl',
  keyword_count INTEGER,
  status TEXT CHECK (status IN ('pending', 'processing', 'ready', 'failed')) DEFAULT 'pending',
  progress INTEGER DEFAULT 0,
  input_file_path TEXT,
  output_file_path TEXT,
  error_log TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS seo_keywords (
  id BIGSERIAL PRIMARY KEY,
  job_id TEXT REFERENCES seo_jobs(job_id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  volume INTEGER,
  kd FLOAT,
  cpc FLOAT,
  position INTEGER,
  current_url TEXT,
  intent TEXT,
  silo TEXT,
  content_type TEXT,
  title_suggestion TEXT,
  primary_source TEXT,
  audience_match TEXT,
  priority TEXT CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW')),
  processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_seo_keywords_job ON seo_keywords(job_id);
CREATE INDEX IF NOT EXISTS idx_seo_jobs_status ON seo_jobs(status);
CREATE INDEX IF NOT EXISTS idx_seo_jobs_created ON seo_jobs(created_at);
