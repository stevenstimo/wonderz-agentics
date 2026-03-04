CREATE TABLE IF NOT EXISTS development_points (
    point_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    agent_role TEXT,
    issue_description TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 1,
    impact TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'AWAITING_APPROVAL', 'IN_TRAINING', 'RESOLVED', 'DISMISSED')),
    proposed_by TEXT,
    evidence_example TEXT,
    source_url TEXT,
    suggested_url TEXT,
    confidence_score FLOAT,
    resolution TEXT,
    approved_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_development_points_status ON development_points(status);
CREATE INDEX IF NOT EXISTS idx_development_points_agent ON development_points(agent_id);
