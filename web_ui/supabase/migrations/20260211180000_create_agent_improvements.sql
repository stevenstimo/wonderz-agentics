create extension if not exists pgcrypto;

create table if not exists agent_improvements (
  id uuid primary key default gen_random_uuid(),
  agent_id text not null,
  agent_name text not null,
  title text not null,
  summary text,
  details text,
  severity text,
  status text default 'open',
  source text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists agent_improvements_agent_id_idx on agent_improvements (agent_id);
create index if not exists agent_improvements_status_idx on agent_improvements (status);
