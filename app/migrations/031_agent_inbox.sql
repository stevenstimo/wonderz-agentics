CREATE TABLE IF NOT EXISTS agent_inbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'info',
    urgency TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'unread',
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_inbox_to_agent ON agent_inbox(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_inbox_status ON agent_inbox(status);
CREATE INDEX IF NOT EXISTS idx_agent_inbox_urgency ON agent_inbox(urgency);
CREATE INDEX IF NOT EXISTS idx_agent_inbox_created ON agent_inbox(created_at DESC);
