create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  project_idea text,
  language text,
  platform text,
  status text,
  created_at timestamp with time zone default now()
);

