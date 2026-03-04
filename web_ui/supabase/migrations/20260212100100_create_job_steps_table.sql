-- Migration: Create job_steps table
create extension if not exists pgcrypto;

create table if not exists job_steps (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references jobs(id) on delete cascade,
  step_index int not null,
  step_name text,
  agent_role text, -- 'copywriter', 'developer', 'reviewer', etc.
  unified_tool text, -- 'read_product', 'write_description', etc.
  status text not null default 'pending', -- 'pending', 'in_progress', 'success', 'failed', 'awaiting_approval'
  input_payload jsonb default '{}'::jsonb,
  output jsonb default '{}'::jsonb,
  tokens_used int default 0,
  timing_ms int default 0,
  requires_approval boolean default false,
  approved_at timestamptz,
  feedback text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

-- Indexes for efficient job step lookups
create index if not exists job_steps_job_id_idx on job_steps (job_id);
create index if not exists job_steps_status_idx on job_steps (status);
create index if not exists job_steps_agent_role_idx on job_steps (agent_role);
create index if not exists job_steps_created_at_idx on job_steps (created_at desc);
