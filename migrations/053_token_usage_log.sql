-- Token usage log per job_step voor CFO rapportage
CREATE TABLE IF NOT EXISTS token_usage_log (
    id              BIGSERIAL PRIMARY KEY,
    job_id          UUID REFERENCES jobs(id) ON DELETE CASCADE,
    job_step_id     UUID REFERENCES job_steps(id) ON DELETE SET NULL,
    agent_id        TEXT,
    step_name       TEXT,
    model           TEXT NOT NULL,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    cache_read_tokens  INTEGER DEFAULT 0,
    total_tokens    INTEGER GENERATED ALWAYS AS
                    (input_tokens + output_tokens + cache_write_tokens + cache_read_tokens) STORED,
    cost_usd        NUMERIC(10, 6) DEFAULT 0,
    recorded_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_token_usage_job ON token_usage_log(job_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_agent ON token_usage_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_recorded ON token_usage_log(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage_log(model);
