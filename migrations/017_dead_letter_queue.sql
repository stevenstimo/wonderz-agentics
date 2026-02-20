-- Fase B Feature 3: Dead letter queue

CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    agent_id TEXT,
    error_message TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_dlq_unresolved ON dead_letter_queue(resolved_at) WHERE resolved_at IS NULL;
