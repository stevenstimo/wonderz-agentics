-- Platform Spec V4: Event model — events tabel voor traceability (sectie 7.1)
-- Vereist: jobs tabel met job_id (PK of UNIQUE)

CREATE TABLE IF NOT EXISTS events (
  event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type  TEXT NOT NULL,
  agent_id    TEXT,
  task_id     TEXT,
  lesson_id   TEXT,
  job_id      UUID REFERENCES jobs(id) ON DELETE SET NULL,
  confidence_score FLOAT,
  payload     JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_type
  ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_task
  ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_job
  ON events(job_id);
CREATE INDEX IF NOT EXISTS idx_events_created
  ON events(created_at DESC);
