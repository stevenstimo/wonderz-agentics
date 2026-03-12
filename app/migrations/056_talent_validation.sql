-- Platform Spec V2: Talent validation columns + validation_decisions + view
ALTER TABLE job_steps
  ADD COLUMN IF NOT EXISTS talent_status TEXT DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS talent_output JSONB,
  ADD COLUMN IF NOT EXISTS talent_delta TEXT,
  ADD COLUMN IF NOT EXISTS talent_blocking_issues TEXT[];

ALTER TABLE job_steps DROP CONSTRAINT IF EXISTS chk_job_steps_talent_status;
ALTER TABLE job_steps ADD CONSTRAINT chk_job_steps_talent_status
  CHECK (talent_status IS NULL OR talent_status IN ('pending', 'approved', 'approved_with_changes', 'rejected'));

-- Audit table (platform spec sectie 14.3) — step_id references job_steps(id)
CREATE TABLE IF NOT EXISTS validation_decisions (
  decision_id BIGSERIAL PRIMARY KEY,
  task_id TEXT,
  step_id UUID REFERENCES job_steps(id) ON DELETE SET NULL,
  talent_agent_id TEXT DEFAULT 'agent:talent',
  check_name TEXT NOT NULL,
  result TEXT CHECK (result IN ('pass', 'fail', 'override')),
  evidence_verified TEXT,
  notes TEXT,
  decided_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vd_step ON validation_decisions(step_id);
CREATE INDEX IF NOT EXISTS idx_vd_task ON validation_decisions(task_id);

-- View (platform spec sectie 19.1)
CREATE OR REPLACE VIEW talent_governance_metrics AS
SELECT
  v.talent_agent_id,
  COUNT(DISTINCT v.step_id) AS total_reviews,
  SUM(CASE WHEN v.result = 'pass' THEN 1 ELSE 0 END)::FLOAT
    / NULLIF(COUNT(*), 0) AS approval_rate,
  SUM(CASE WHEN v.evidence_verified IS NOT NULL THEN 1 ELSE 0 END)::FLOAT
    / NULLIF(COUNT(*), 0) AS evidence_verification_rate,
  CASE
    WHEN SUM(CASE WHEN v.result = 'pass' THEN 1 ELSE 0 END)::FLOAT
         / NULLIF(COUNT(*), 0) > 0.85
    THEN 'HIGH_RISK_RUBBER_STAMP'
    ELSE 'NORMAL'
  END AS monitoring_status
FROM validation_decisions v
GROUP BY v.talent_agent_id;
