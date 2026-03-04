-- Fase C Feature 3: Scheduled jobs

CREATE TABLE IF NOT EXISTS job_schedules (
    schedule_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    template_id TEXT REFERENCES job_templates(template_id),
    job_config JSONB NOT NULL,
    cron_expression TEXT NOT NULL,
    timezone TEXT DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT true,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    run_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON job_schedules(next_run_at)
WHERE is_active = true;
