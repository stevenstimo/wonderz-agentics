-- File Output in Job Environment: downloadbare Word/Excel als onderdeel van job flow
-- Run: psql "$DATABASE_URL" -f app/migrations/035_job_file_artifacts.sql

ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS file_artifact_path TEXT,
ADD COLUMN IF NOT EXISTS file_artifact_type TEXT CHECK (
  file_artifact_type IN ('docx', 'xlsx', 'pdf')
),
ADD COLUMN IF NOT EXISTS file_artifact_name TEXT;
