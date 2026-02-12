-- Migration: Create clarifications table for intake Q&A
create extension if not exists pgcrypto;

create table if not exists clarifications (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references jobs(id) on delete cascade,
  question_id text not null unique,
  question text not null,
  user_answer text,
  asked_at timestamptz not null default now(),
  answered_at timestamptz,
  round_number int default 1
);

-- Indexes
create index if not exists clarifications_job_id_idx on clarifications (job_id);
create index if not exists clarifications_answered_at_idx on clarifications (answered_at);
