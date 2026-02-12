alter table if exists crew_members
  add column if not exists system_instructions text,
  add column if not exists knowledge_base_sources jsonb default '[]'::jsonb,
  add column if not exists tool_access_whitelist jsonb default '[]'::jsonb,
  add column if not exists hiring_logic text;

alter table if exists ceo_hired_agents
  add column if not exists system_instructions text,
  add column if not exists knowledge_base_sources jsonb default '[]'::jsonb,
  add column if not exists tool_access_whitelist jsonb default '[]'::jsonb,
  add column if not exists hiring_logic text;

create table if not exists hired_agents (
  id uuid primary key default gen_random_uuid(),
  agent_id text unique not null,
  name text not null,
  role text not null,
  specialization text,
  status text default 'active',
  permissions jsonb default '[]'::jsonb,
  system_instructions text,
  knowledge_base_sources jsonb default '[]'::jsonb,
  tool_access_whitelist jsonb default '[]'::jsonb,
  hiring_logic text,
  performance_score float default 0.0,
  completed_tasks int default 0,
  hired_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists hired_agents_role_idx on hired_agents (role);
create index if not exists hired_agents_status_idx on hired_agents (status);
create index if not exists hired_agents_agent_id_idx on hired_agents (agent_id);
