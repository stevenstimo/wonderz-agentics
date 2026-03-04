CREATE TABLE IF NOT EXISTS training_requests (
    request_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    confidence_score FLOAT,
    suggested_url TEXT,
    status TEXT CHECK (status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    approved_by TEXT,
    approval_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_training_requests_status ON training_requests(status);
CREATE INDEX IF NOT EXISTS idx_training_requests_agent ON training_requests(agent_id);
