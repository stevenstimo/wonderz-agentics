-- Migration: Create artifacts table for storing original vs proposed data
create extension if not exists pgcrypto;

create table if not exists artifacts (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references jobs(id) on delete cascade,
  step_id uuid references job_steps(id) on delete set null,
  artifact_type text not null, -- 'product', 'ad', 'content', 'diff', etc.
  name text,
  original_data jsonb default '{}'::jsonb,
  proposed_data jsonb default '{}'::jsonb,
  review_feedback text,
  storage_path text, -- for files stored in S3 or similar
  created_at timestamptz not null default now()
);

-- Indexes
create index if not exists artifacts_job_id_idx on artifacts (job_id);
create index if not exists artifacts_type_idx on artifacts (artifact_type);
create index if not exists artifacts_created_at_idx on artifacts (created_at desc);
