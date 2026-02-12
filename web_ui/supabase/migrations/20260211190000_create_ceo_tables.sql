create extension if not exists pgcrypto;

create table if not exists ceo_hired_agents (
  id uuid primary key default gen_random_uuid(),
  agent_id text unique not null,
  name text not null,
  role text not null,
  specialization text,
  status text default 'active',
  permissions jsonb default '[]'::jsonb,
  performance_score float default 0.0,
  completed_tasks int default 0,
  hired_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists ceo_approval_requests (
  id uuid primary key default gen_random_uuid(),
  approval_id text unique not null,
  request_type text not null,
  status text default 'pending',
  details jsonb,
  requested_at timestamptz not null default now(),
  approved_at timestamptz,
  rejected_at timestamptz
);

create index if not exists ceo_hired_agents_role_idx on ceo_hired_agents (role);
create index if not exists ceo_hired_agents_status_idx on ceo_hired_agents (status);
create index if not exists ceo_approval_requests_status_idx on ceo_approval_requests (status);
