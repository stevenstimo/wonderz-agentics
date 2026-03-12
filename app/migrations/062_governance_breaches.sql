-- Platform Spec V7: Governance Monitoring — breach log and (optional) agents columns

-- Governance breach log
CREATE TABLE IF NOT EXISTS governance_breaches (
  breach_id       UUID PRIMARY KEY
                    DEFAULT gen_random_uuid(),
  talent_agent_id TEXT,
  domain          TEXT,
  approval_rate   FLOAT,
  evidence_verification_rate FLOAT,
  breach_type     TEXT CHECK (breach_type IN (
    'HIGH_RISK_RUBBER_STAMP',
    'LOW_EVIDENCE_VERIFICATION'
  )),
  action_taken    TEXT CHECK (action_taken IN (
    'suspended','notified','ignored'
  )),
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gb_agent
  ON governance_breaches(talent_agent_id);
CREATE INDEX IF NOT EXISTS idx_gb_created
  ON governance_breaches(created_at DESC);
