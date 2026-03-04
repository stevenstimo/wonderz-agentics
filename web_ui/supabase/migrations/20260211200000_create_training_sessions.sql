create extension if not exists pgcrypto;

create table if not exists training_sessions (
  id uuid primary key default gen_random_uuid(),
  session_id text unique not null,
  crew_id text not null,
  agent_name text not null,
  training_url text not null,
  training_title text,
  training_summary text,
  knowledge_base text,
  status text default 'pending',
  approval_status text default 'pending',
  requested_at timestamptz not null default now(),
  approved_at timestamptz,
  completed_at timestamptz,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists training_sessions_crew_id_idx on training_sessions (crew_id);
create index if not exists training_sessions_status_idx on training_sessions (status);
create index if not exists training_sessions_approval_idx on training_sessions (approval_status);
