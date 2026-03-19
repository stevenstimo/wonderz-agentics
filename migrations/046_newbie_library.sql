-- Migration 046: Newbie Library (URL scrape once, per-Newbie decisions)
-- Run: psql "$DATABASE_URL" -f migrations/046_newbie_library.sql

-- Centrale bibliotheek: één rij per URL
CREATE TABLE IF NOT EXISTS newbie_library (
  library_id BIGSERIAL PRIMARY KEY,
  source_url TEXT NOT NULL UNIQUE,
  title TEXT,
  summary TEXT,
  full_text TEXT NOT NULL,
  added_by TEXT DEFAULT 'admin',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Per Newbie: beslissing over een library item
CREATE TABLE IF NOT EXISTS newbie_library_decisions (
  decision_id BIGSERIAL PRIMARY KEY,
  newbie_id TEXT NOT NULL REFERENCES newbies(newbie_id) ON DELETE CASCADE,
  library_id BIGINT NOT NULL REFERENCES newbie_library(library_id) ON DELETE CASCADE,
  accept BOOLEAN NOT NULL,
  category TEXT,
  reason TEXT,
  confidence FLOAT DEFAULT 0.0,
  score_gained INTEGER DEFAULT 0,
  decided_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(newbie_id, library_id)
);

CREATE INDEX IF NOT EXISTS idx_library_decisions_newbie
  ON newbie_library_decisions(newbie_id);

CREATE INDEX IF NOT EXISTS idx_library_decisions_library
  ON newbie_library_decisions(library_id);

