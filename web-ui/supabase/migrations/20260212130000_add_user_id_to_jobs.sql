alter table if exists jobs
  add column if not exists user_id uuid;

create index if not exists jobs_user_id_idx on jobs (user_id);
