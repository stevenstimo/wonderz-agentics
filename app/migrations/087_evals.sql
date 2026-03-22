-- Eval infrastructure: regression + capability suites, runs, per-case results.
-- Applied: 2026-03

CREATE TABLE IF NOT EXISTS eval_suites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    suite_type TEXT NOT NULL CHECK (suite_type IN ('regression', 'capability')),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_id UUID REFERENCES eval_suites(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    input_payload JSONB NOT NULL,
    expected_checks JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_id UUID REFERENCES eval_suites(id),
    triggered_by TEXT DEFAULT 'manual',
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    total_cases INTEGER DEFAULT 0,
    passed_cases INTEGER DEFAULT 0,
    failed_cases INTEGER DEFAULT 0,
    pass_rate FLOAT,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    summary JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS eval_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES eval_runs(id) ON DELETE CASCADE,
    case_id UUID REFERENCES eval_cases(id),
    job_id UUID REFERENCES jobs(id),
    passed BOOLEAN,
    checks_passed JSONB DEFAULT '[]'::jsonb,
    checks_failed JSONB DEFAULT '[]'::jsonb,
    duration_seconds FLOAT,
    error_detail TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eval_results_run ON eval_results(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_cases_suite ON eval_cases(suite_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_started ON eval_runs(started_at DESC);
