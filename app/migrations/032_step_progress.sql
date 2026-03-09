-- Migration: Step-level progress tracking
-- Add progress_pct to job_steps for per-step progress bar (10% start, 70% after LLM, 100% done).
-- Run on server: psql "$DATABASE_URL" -f app/migrations/032_step_progress.sql

ALTER TABLE job_steps ADD COLUMN IF NOT EXISTS progress_pct INTEGER DEFAULT 0;
