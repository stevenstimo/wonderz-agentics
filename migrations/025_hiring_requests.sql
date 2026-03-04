CREATE TABLE IF NOT EXISTS hiring_requests (
    request_id TEXT PRIMARY KEY,
    job_id UUID REFERENCES jobs(id),
    required_role TEXT NOT NULL,
    task_type TEXT,
    status TEXT CHECK (status IN ('pending', 'in_progress', 'hired', 'cancelled')) DEFAULT 'pending',
    hired_agent_id TEXT REFERENCES hired_agents(agent_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_hiring_requests_status ON hiring_requests(status);
CREATE INDEX IF NOT EXISTS idx_hiring_requests_role ON hiring_requests(required_role);
