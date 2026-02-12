-- Migration: Create jobs table for the job flow
create extension if not exists pgcrypto;

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  job_post text not null,
  status text not null default 'INTAKE_CLARIFICATION',
  source_platform text, -- 'shopify', 'wordpress', etc.
  context jsonb default '{}'::jsonb, -- stores the StrategicBrief, ExecutionPlan, etc.
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Add index for status and user_id for quick lookups
create index if not exists jobs_status_idx on jobs (status);
create index if not exists jobs_created_at_idx on jobs (created_at desc);
