-- Migration: Newbies & Newbie Trainings
-- Crew Intelligent Spec v1.0: Newbie pool met readiness-scoring, training flow, hire naar hired_agents.
-- Run: psql "$DATABASE_URL" -f migrations/029_newbies.sql

-- Newbies: persona's in ontwikkeling, nog niet inzetbaar als agent
CREATE TABLE IF NOT EXISTS newbies (
  newbie_id        TEXT PRIMARY KEY,
  newbie_name      TEXT NOT NULL,
  persona          TEXT NOT NULL,
  qualities        TEXT NOT NULL,
  development      TEXT NOT NULL,

  -- Readiness scoring (0-100 per category, max 80 via training; laatste 20 via hire)
  readiness_score  INTEGER DEFAULT 0 CHECK (readiness_score >= 0 AND readiness_score <= 100),
  score_management INTEGER DEFAULT 0 CHECK (score_management >= 0 AND score_management <= 100),
  score_creative   INTEGER DEFAULT 0 CHECK (score_creative >= 0 AND score_creative <= 100),
  score_development INTEGER DEFAULT 0 CHECK (score_development >= 0 AND score_development <= 100),
  score_operations INTEGER DEFAULT 0 CHECK (score_operations >= 0 AND score_operations <= 100),

  -- Status
  status           TEXT NOT NULL DEFAULT 'in_training' CHECK (status IN (
    'in_training',
    'ready',
    'hired',
    'inactive'
  )),

  -- Relaties
  hired_as         TEXT REFERENCES hired_agents(agent_id),
  suggested_role   TEXT,

  created_at       TIMESTAMPTZ DEFAULT now(),
  updated_at       TIMESTAMPTZ DEFAULT now()
);

-- Trainingen per Newbie (max 80 punten per category via training)
CREATE TABLE IF NOT EXISTS newbie_trainings (
  training_id      BIGSERIAL PRIMARY KEY,
  newbie_id        TEXT NOT NULL REFERENCES newbies(newbie_id) ON DELETE CASCADE,
  source_url       TEXT NOT NULL,
  category         TEXT NOT NULL CHECK (category IN (
    'management', 'creative', 'development', 'operations'
  )),
  score_gained     INTEGER DEFAULT 0,
  status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
  completed_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ DEFAULT now()
);

-- Indexen voor snelle queries
CREATE INDEX IF NOT EXISTS idx_newbies_status ON newbies(status);
CREATE INDEX IF NOT EXISTS idx_newbies_readiness ON newbies(readiness_score) WHERE status = 'ready';
CREATE INDEX IF NOT EXISTS idx_newbie_trainings_newbie_id ON newbie_trainings(newbie_id);
CREATE INDEX IF NOT EXISTS idx_newbie_trainings_category ON newbie_trainings(newbie_id, category);
