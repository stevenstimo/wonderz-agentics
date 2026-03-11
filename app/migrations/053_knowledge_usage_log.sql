CREATE TABLE IF NOT EXISTS knowledge_usage_log (
  log_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id        UUID REFERENCES jobs(id) ON DELETE CASCADE,
  step_id       UUID REFERENCES job_steps(id) ON DELETE SET NULL,
  agent_id      TEXT,
  document_ids  TEXT[] DEFAULT '{}',
  lesson_ids    TEXT[] DEFAULT '{}',
  chunks_used   INTEGER DEFAULT 0,
  lessons_used  INTEGER DEFAULT 0,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kul_job ON knowledge_usage_log(job_id);
CREATE INDEX IF NOT EXISTS idx_kul_agent ON knowledge_usage_log(agent_id);
