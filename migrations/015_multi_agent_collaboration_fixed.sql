-- Multi-agent collaboration tables (type-fixed)

CREATE TABLE IF NOT EXISTS agent_teams (
    team_id TEXT PRIMARY KEY,
    job_id UUID NOT NULL,  -- Changed from TEXT to UUID
    agents JSONB NOT NULL,
    coordination_strategy TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shared_job_context (
    context_id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL,  -- Changed from TEXT to UUID
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    contributed_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(job_id, key)
);

CREATE INDEX IF NOT EXISTS idx_shared_context_job ON shared_job_context(job_id);
