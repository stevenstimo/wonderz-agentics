CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('Worker', 'Talent')),
    specialization TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    is_suspended BOOLEAN DEFAULT false,
    suspended_at TIMESTAMPTZ,
    suspension_reason TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(agent_id),
    title TEXT NOT NULL,
    status TEXT CHECK (status IN ('open', 'done', 'blocked')) DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS platform_artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    locator TEXT NOT NULL,
    checksum TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS artifact_versions (
    version_id BIGSERIAL PRIMARY KEY,
    artifact_id TEXT REFERENCES platform_artifacts(artifact_id),
    git_commit TEXT NOT NULL,
    committed_at TIMESTAMPTZ,
    checksum TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS citations (
    citation_id BIGSERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
    artifact_ref TEXT,
    location TEXT,
    excerpt_summary TEXT,
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    git_commit TEXT,
    symbol_name TEXT,
    is_stale BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_citations_file_path ON citations(file_path);
CREATE INDEX IF NOT EXISTS idx_citations_task ON citations(task_id);

CREATE TABLE IF NOT EXISTS findings (
    finding_id BIGSERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS causes (
    cause_id BIGSERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fixes (
    fix_id BIGSERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    diff_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id BIGSERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    details TEXT,
    status TEXT CHECK (status IN ('planned', 'passed', 'failed')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    agent_id TEXT REFERENCES agents(agent_id),
    task_id TEXT REFERENCES tasks(task_id),
    title TEXT NOT NULL,
    gevonden TEXT NOT NULL,
    oorzaak TEXT NOT NULL,
    fix TEXT NOT NULL,
    impact TEXT,
    confidence_score NUMERIC(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    status TEXT CHECK (status IN ('pending', 'active', 'rejected', 'superseded', 'invalidated', 'stale')) DEFAULT 'pending',
    usage_count INTEGER DEFAULT 0,
    last_confirmed_at TIMESTAMPTZ,
    superseded_by TEXT REFERENCES lessons(lesson_id),
    submitted_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    version_token INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_lessons_agent ON lessons(agent_id);
CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons(status);
CREATE INDEX IF NOT EXISTS idx_lessons_confidence ON lessons(confidence_score);

ALTER TABLE lessons ADD COLUMN IF NOT EXISTS embedding vector(1536);
CREATE INDEX IF NOT EXISTS idx_lessons_embedding ON lessons USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS patterns (
    pattern_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pattern_type TEXT CHECK (pattern_type IN ('pattern', 'anti_pattern')),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lesson_patterns (
    lesson_id TEXT REFERENCES lessons(lesson_id) ON DELETE CASCADE,
    pattern_id TEXT REFERENCES patterns(pattern_id) ON DELETE CASCADE,
    PRIMARY KEY (lesson_id, pattern_id)
);

CREATE TABLE IF NOT EXISTS lesson_tags (
    lesson_id TEXT REFERENCES lessons(lesson_id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (lesson_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_lesson_tags_tag ON lesson_tags(tag);

CREATE TABLE IF NOT EXISTS validation_decisions (
    decision_id BIGSERIAL PRIMARY KEY,
    task_id TEXT REFERENCES tasks(task_id),
    talent_agent_id TEXT REFERENCES agents(agent_id),
    check_name TEXT NOT NULL,
    result TEXT CHECK (result IN ('pass', 'fail', 'override')),
    evidence_verified TEXT,
    notes TEXT,
    decided_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_validation_decisions_talent ON validation_decisions(talent_agent_id);
CREATE INDEX IF NOT EXISTS idx_validation_decisions_task ON validation_decisions(task_id);

CREATE OR REPLACE VIEW talent_approval_rates AS
SELECT talent_agent_id,
    COUNT(*) AS total_reviews,
    SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS approval_rate
FROM validation_decisions
GROUP BY talent_agent_id;

CREATE OR REPLACE VIEW talent_governance_metrics AS
SELECT
    v.talent_agent_id,
    a.specialization AS domain,
    COUNT(DISTINCT v.task_id) AS total_reviews,
    SUM(CASE WHEN v.result = 'pass' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS approval_rate,
    SUM(CASE WHEN v.evidence_verified IS NOT NULL THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS evidence_verification_rate,
    AVG(l.confidence_score) AS avg_confidence_given,
    CASE WHEN SUM(CASE WHEN v.result = 'pass' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) > 0.85
        THEN 'HIGH_RISK_RUBBER_STAMP' ELSE 'NORMAL' END AS monitoring_status
FROM validation_decisions v
JOIN agents a ON v.talent_agent_id = a.agent_id
LEFT JOIN lessons l ON v.task_id = l.task_id
GROUP BY v.talent_agent_id, a.specialization;

CREATE TABLE IF NOT EXISTS lesson_conflicts (
    conflict_id BIGSERIAL PRIMARY KEY,
    lesson_a TEXT REFERENCES lessons(lesson_id),
    lesson_b TEXT REFERENCES lessons(lesson_id),
    detected_at TIMESTAMPTZ DEFAULT now(),
    resolved_by TEXT REFERENCES agents(agent_id),
    resolution TEXT CHECK (resolution IN ('a_prevails', 'b_prevails', 'both_invalidated', 'merged')),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS graph_edges (
    edge_id BIGSERIAL PRIMARY KEY,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    attrs JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_graph_edges_from ON graph_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_to ON graph_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_type ON graph_edges(edge_type);

INSERT INTO agents (agent_id, agent_type, specialization)
VALUES
    ('agent:talent-validator', 'Talent', 'validation'),
    ('agent:frontend-engineer', 'Worker', 'frontend'),
    ('agent:backend-engineer', 'Worker', 'backend'),
    ('agent:qa-engineer', 'Worker', 'qa')
ON CONFLICT (agent_id) DO NOTHING;
