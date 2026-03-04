create type app_role as enum ('member', 'super_admin');

create table if not exists user_roles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role app_role not null default 'member',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function set_user_roles_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_user_roles_updated_at on user_roles;
create trigger trg_user_roles_updated_at
before update on user_roles
for each row
execute function set_user_roles_updated_at();

alter table user_roles enable row level security;

drop policy if exists user_roles_select_own on user_roles;
create policy user_roles_select_own
on user_roles
for select
to authenticated
using (auth.uid() = user_id);

insert into user_roles (user_id, role)
select id, 'member'::app_role
from auth.users
on conflict (user_id) do nothing;

insert into user_roles (user_id, role)
select id, 'super_admin'::app_role
from auth.users
where lower(email) = 'stevenstimo@gmail.com'
on conflict (user_id)
do update set role = excluded.role, updated_at = now();
