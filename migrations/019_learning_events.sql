-- Fase A Feature 3: Cross-agent learning events

CREATE TABLE IF NOT EXISTS learning_events (
    event_id BIGSERIAL PRIMARY KEY,
    source_agent_id TEXT NOT NULL REFERENCES hired_agents(agent_id),
    skill_id TEXT NOT NULL REFERENCES agent_skills(skill_id),
    target_role TEXT NOT NULL,
    propagated_to INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_events_agent ON learning_events(source_agent_id);
CREATE INDEX IF NOT EXISTS idx_learning_events_created ON learning_events(created_at DESC);
