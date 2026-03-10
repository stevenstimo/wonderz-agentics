-- Migration: Add extracted_summary to newbie_trainings for tooltip in trainingshistorie
-- Run: psql "$DATABASE_URL" -f migrations/032_newbie_trainings_extracted_summary.sql

ALTER TABLE newbie_trainings ADD COLUMN IF NOT EXISTS extracted_summary TEXT;
