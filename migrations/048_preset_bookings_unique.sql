-- Migration 048: unieke boeking per job/preset/slot voor idempotente INSERT ... ON CONFLICT DO NOTHING
-- Run: psql "$DATABASE_URL" -f migrations/048_preset_bookings_unique.sql

CREATE UNIQUE INDEX IF NOT EXISTS uq_preset_bookings_job_preset_slot
  ON preset_bookings (job_id, preset_id, slot_role);
