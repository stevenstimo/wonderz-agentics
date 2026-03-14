-- Migration: system_events
-- Doel: Operationele fouten van de CEO/orchestrator loggen.
-- Scheiding: development_points = agent-kwaliteit (HR flow)
--            system_events = platform-gezondheid (operator monitoring)

CREATE TABLE IF NOT EXISTS system_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL,
    -- Mogelijke waarden:
    --   orchestrator_error     CEO kon geen plan genereren of is gecrasht
    --   token_budget_exceeded  Job overschreed het token budget (sectie 3.4 product spec)
    --   job_stalled            Job staat langer dan drempelwaarde in dezelfde status
    --   agent_timeout          Een agent heeft niet gereageerd binnen de timeout
    --   validation_loop        Talent heeft 3+ keer rejected zonder resolution
    --   intake_loop_detected   CEO bleef vragen stellen voorbij max rondes
    --   tool_failure           Een tool-aanroep is gefaald (naam in details)
    --   system_warning         Overige waarschuwingen van het platform

    severity        TEXT NOT NULL DEFAULT 'warning',
    -- Mogelijke waarden: info | warning | error | critical

    job_id          UUID REFERENCES jobs(id) ON DELETE SET NULL,
    -- NULL als het event niet job-gebonden is (bijv. platform-startup fout)

    agent_id        TEXT REFERENCES hired_agents(agent_id) ON DELETE SET NULL,
    -- De agent (inclusief CEO) die het event heeft veroorzaakt

    message         TEXT NOT NULL,
    -- Leesbare samenvatting: "CEO kon geen plan genereren voor job X"

    details         JSONB DEFAULT '{}',
    -- Gestructureerde technische details:
    -- { "error": "...", "token_count": 18500, "budget": 20000,
    --   "step_id": "...", "retry_count": 3, "tool_name": "..." }

    resolved        BOOLEAN DEFAULT false,
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    -- 'operator' of agent_id die het event heeft opgelost

    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Indexen voor veelgebruikte queries
CREATE INDEX IF NOT EXISTS idx_system_events_job_id
    ON system_events(job_id);

CREATE INDEX IF NOT EXISTS idx_system_events_event_type
    ON system_events(event_type);

CREATE INDEX IF NOT EXISTS idx_system_events_severity
    ON system_events(severity);

CREATE INDEX IF NOT EXISTS idx_system_events_resolved
    ON system_events(resolved) WHERE resolved = false;

CREATE INDEX IF NOT EXISTS idx_system_events_created_at
    ON system_events(created_at DESC);

COMMENT ON TABLE system_events IS
    'Operationele events van de CEO/orchestrator en het platform. '
    'Niet te verwarren met development_points (agent-kwaliteit, HR flow). '
    'system_events zijn voor platform-monitoring door de menselijke operator.';
