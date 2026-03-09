CREATE TABLE IF NOT EXISTS newbies (
  newbie_id TEXT PRIMARY KEY,
  newbie_name TEXT NOT NULL,
  persona TEXT NOT NULL,
  qualities TEXT NOT NULL,
  development TEXT NOT NULL,
  readiness_score INTEGER DEFAULT 0,
  score_management INTEGER DEFAULT 0,
  score_creative INTEGER DEFAULT 0,
  score_development INTEGER DEFAULT 0,
  score_operations INTEGER DEFAULT 0,
  status TEXT CHECK (status IN ('in_training','ready','hired','inactive')) DEFAULT 'in_training',
  hired_as TEXT REFERENCES hired_agents(agent_id),
  suggested_role TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS newbie_trainings (
  training_id BIGSERIAL PRIMARY KEY,
  newbie_id TEXT REFERENCES newbies(newbie_id),
  source_url TEXT,
  category TEXT CHECK (category IN ('management','creative','development','operations')),
  score_gained INTEGER DEFAULT 0,
  status TEXT CHECK (status IN ('pending','completed','failed')) DEFAULT 'pending',
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_newbies_status ON newbies(status);
CREATE INDEX IF NOT EXISTS idx_newbies_readiness ON newbies(readiness_score);
CREATE INDEX IF NOT EXISTS idx_newbie_trainings_newbie ON newbie_trainings(newbie_id);
