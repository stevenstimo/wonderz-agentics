create extension if not exists pgcrypto;

create table if not exists crew_members (
  id uuid primary key default gen_random_uuid(),
  crew_id text unique not null,
  name text not null,
  role text not null,
  specialization text,
  status text default 'active',
  permissions jsonb default '[]'::jsonb,
  performance_score float default 0.0,
  completed_tasks int default 0,
  current_task text,
  progress int default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists crew_members_role_idx on crew_members (role);
create index if not exists crew_members_status_idx on crew_members (status);
create index if not exists crew_members_crew_id_idx on crew_members (crew_id);
