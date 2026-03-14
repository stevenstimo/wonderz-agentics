# CURSOR PROMPT: CEO Issue Tracking via system_events

**Feature:** System Events tabel voor CEO/orchestrator logging  
**Context:** Crew Intelligent, Crew Intelligent Product Spec v1.1 + Platform Spec v1.3  
**Tool:** Cursor (Wonderz-Agentics repo)  
**Prioriteit:** Robuuste, duurzame implementatie. Geen quick fixes.

---

## 0. ARCHITECTURELE BESLISSING (lees dit eerst)

CEO/orchestrator-fouten zijn **geen development points**. De `development_points` tabel is ontworpen voor agent-kwaliteitsproblemen die via de HR Manager worden gedetecteerd en via de CEO worden goedgekeurd. Als de CEO zelf een fout heeft, werkt die approval-flow niet: de CEO kan zijn eigen issues niet goedkeuren.

**Gekozen oplossing: Optie B + lichte Optie C**

- **Optie B:** Aparte `system_events` tabel voor orchestrator-fouten. Zichtbaar voor de menselijke operator, niet via HR approval flow.
- **Optie C (licht):** Job-detail view linkt direct naar het relevante system_event van die job. Geen aparte navigatie nodig voor job-specifieke fouten.

Dit houdt HR overzichtelijk voor waar het voor bedoeld is (agent-groei), en geeft een schone plek voor platform-monitoring.

---

## 1. PRE-FLIGHT CHECKLIST

Voer deze checks uit voordat je begint. Stop bij een fout en meld dit.

```sql
-- 1. Verifieer dat jobs tabel bestaat met UUID primary key
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'jobs' AND column_name = 'id';

-- 2. Verifieer dat job_steps tabel bestaat
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'job_steps' LIMIT 5;

-- 3. Verifieer dat hired_agents tabel bestaat (inclusief CEO agent)
SELECT agent_id, role FROM hired_agents WHERE role = 'ceo';

-- 4. Verifieer dat development_points tabel bestaat (niet aanraken)
SELECT COUNT(*) FROM development_points;

-- 5. Controleer of system_events al bestaat (voor herrun-veiligheid)
SELECT EXISTS (
  SELECT FROM information_schema.tables 
  WHERE table_name = 'system_events'
);
```

---

## 2. DATABASE MIGRATIE

Maak het bestand `app/migrations/0XX_system_events.sql` aan.  
Vervang `0XX` met het volgende migratienummer in de reeks.

```sql
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
```

**Voer de migratie uit op de server (Shelley):**
```bash
psql "$DATABASE_URL" -f app/migrations/0XX_system_events.sql
```

**Verifieer na uitvoering:**
```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'system_events'
ORDER BY ordinal_position;
```

---

## 3. BACKEND: SystemEventsService

Maak het bestand `app/services/system_events_service.py` aan.

```python
"""
SystemEventsService
-------------------
Verantwoordelijk voor het loggen van operationele platform-events.

Architectuurnoot: Dit is GEEN vervanging van development_points.
- development_points  = agent-kwaliteitsproblemen, HR approval flow
- system_events       = orchestrator/platform fouten, operator monitoring

Gebruik: await system_events_service.log_event(...)
"""

import json
import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class SystemEventsService:

    # Event types (canonieke waarden, gebruik deze constanten)
    ORCHESTRATOR_ERROR    = "orchestrator_error"
    TOKEN_BUDGET_EXCEEDED = "token_budget_exceeded"
    JOB_STALLED           = "job_stalled"
    AGENT_TIMEOUT         = "agent_timeout"
    VALIDATION_LOOP       = "validation_loop"
    INTAKE_LOOP_DETECTED  = "intake_loop_detected"
    TOOL_FAILURE          = "tool_failure"
    SYSTEM_WARNING        = "system_warning"

    # Severity levels
    INFO     = "info"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"

    def __init__(self, db_pool):
        self.pool = db_pool

    async def log_event(
        self,
        event_type: str,
        message: str,
        severity: str = "warning",
        job_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Log een system event. Geeft het event_id terug, of None bij fout.
        Faalt altijd stilletjes: een logfout mag de normale flow nooit breken.
        """
        try:
            async with self.pool.acquire() as conn:
                event_id = await conn.fetchval(
                    """
                    INSERT INTO system_events 
                        (event_type, severity, job_id, agent_id, message, details)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING event_id
                    """,
                    event_type,
                    severity,
                    job_id,
                    agent_id,
                    message,
                    json.dumps(details or {}),
                )
                logger.info(
                    f"[SystemEvent] {severity.upper()} | {event_type} | "
                    f"job={job_id} | agent={agent_id} | {message}"
                )
                return str(event_id)
        except Exception as e:
            # Nooit een exception gooien vanuit logging
            logger.error(f"[SystemEventsService] Kon event niet loggen: {e}")
            return None

    async def resolve_event(
        self,
        event_id: str,
        resolved_by: str = "operator",
    ) -> bool:
        """Markeer een event als opgelost."""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE system_events 
                    SET resolved = true, 
                        resolved_at = now(), 
                        resolved_by = $2
                    WHERE event_id = $1 AND resolved = false
                    """,
                    event_id,
                    resolved_by,
                )
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"[SystemEventsService] Kon event niet resolven: {e}")
            return False

    async def get_events(
        self,
        job_id: Optional[str] = None,
        unresolved_only: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """Haal events op, optioneel gefilterd op job of openstaand."""
        try:
            async with self.pool.acquire() as conn:
                conditions = []
                params = []

                if job_id:
                    params.append(job_id)
                    conditions.append(f"job_id = ${len(params)}")

                if unresolved_only:
                    conditions.append("resolved = false")

                where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                params.append(limit)

                rows = await conn.fetch(
                    f"""
                    SELECT event_id, event_type, severity, job_id, agent_id,
                           message, details, resolved, resolved_at, resolved_by,
                           created_at
                    FROM system_events
                    {where}
                    ORDER BY created_at DESC
                    LIMIT ${len(params)}
                    """,
                    *params,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[SystemEventsService] Kon events niet ophalen: {e}")
            return []
```

---

## 4. INTEGRATIE IN BESTAANDE CODE

### 4.1 Initialiseer de service in main.py

Voeg toe aan de startup van de applicatie (bij de andere service-initialisaties):

```python
from app.services.system_events_service import SystemEventsService

# In de lifespan of startup handler, naast andere services:
app.state.system_events = SystemEventsService(db_pool)
```

### 4.2 Logging in de CEO/orchestrator

Zoek de CEO-orchestrator code (waarschijnlijk in `app/agents/ceo_agent.py` of equivalent). Voeg logging toe op de volgende punten:

**Bij orchestrator error (plan-generatie mislukt):**
```python
except Exception as e:
    await request.app.state.system_events.log_event(
        event_type=SystemEventsService.ORCHESTRATOR_ERROR,
        severity=SystemEventsService.ERROR,
        job_id=str(job_id),
        agent_id="agent:ceo",
        message=f"CEO kon geen plan genereren voor job {job_id}",
        details={"error": str(e), "traceback": traceback.format_exc()},
    )
    raise  # Gooi de exception wel opnieuw voor de normale error handling
```

**Bij token budget overschrijding (zie Product Spec v1.1 sectie 3.4):**
```python
if token_count >= HARD_BLOCK_LIMIT:
    await request.app.state.system_events.log_event(
        event_type=SystemEventsService.TOKEN_BUDGET_EXCEEDED,
        severity=SystemEventsService.CRITICAL,
        job_id=str(job_id),
        agent_id="agent:ceo",
        message=f"Token budget overschreden voor job {job_id}: {token_count}/{HARD_BLOCK_LIMIT}",
        details={"token_count": token_count, "budget": HARD_BLOCK_LIMIT},
    )
```

**Bij intake loop (max rondes bereikt):**
```python
if round_count >= MAX_INTAKE_ROUNDS:
    await request.app.state.system_events.log_event(
        event_type=SystemEventsService.INTAKE_LOOP_DETECTED,
        severity=SystemEventsService.WARNING,
        job_id=str(job_id),
        agent_id="agent:ceo",
        message=f"Intake loop gestopt na {round_count} rondes voor job {job_id}",
        details={"rounds": round_count, "max_rounds": MAX_INTAKE_ROUNDS},
    )
```

**Bij validation loop (Talent 3x rejected):**
```python
if retry_count >= 3:
    await request.app.state.system_events.log_event(
        event_type=SystemEventsService.VALIDATION_LOOP,
        severity=SystemEventsService.ERROR,
        job_id=str(job_id),
        agent_id=agent_id,
        message=f"Agent {agent_id} heeft 3x een rejected output geproduceerd voor job {job_id}",
        details={"retry_count": retry_count, "last_feedback": feedback},
    )
```

**Zoekstrategie in de codebase:**
```
Zoek naar: MAX_INTAKE_ROUNDS, budget_exceeded, HARD_BLOCK_LIMIT, 
           reviewer_agent, NEEDS_CHANGES, retry_count
```
Log op alle plekken waar nu een exception wordt gegooid of een status naar `failed`/`budget_exceeded` gaat.

---

## 5. API ENDPOINTS

Voeg toe aan het bestaande router-bestand (waarschijnlijk `app/api/routes.py` of equivalent):

```python
from app.services.system_events_service import SystemEventsService

# GET /api/system-events
# Alle events, optioneel gefilterd. Voor het platform-overzicht.
@router.get("/system-events")
async def get_system_events(
    unresolved_only: bool = False,
    limit: int = 50,
    request: Request = None,
):
    events = await request.app.state.system_events.get_events(
        unresolved_only=unresolved_only,
        limit=limit,
    )
    return {"events": events, "count": len(events)}


# GET /api/jobs/{job_id}/system-events
# Events voor een specifieke job. Gebruikt door de job-detail view.
@router.get("/jobs/{job_id}/system-events")
async def get_job_system_events(job_id: str, request: Request):
    events = await request.app.state.system_events.get_events(
        job_id=job_id,
    )
    return {"events": events, "count": len(events)}


# PATCH /api/system-events/{event_id}/resolve
# Markeer een event als opgelost (door de menselijke operator).
@router.patch("/system-events/{event_id}/resolve")
async def resolve_system_event(event_id: str, request: Request):
    success = await request.app.state.system_events.resolve_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event niet gevonden of al opgelost")
    return {"resolved": True, "event_id": event_id}
```

---

## 6. FRONTEND

### 6.1 SystemEventsBadge (voor in de navigatie)

Maak `web_ui/frontend/src/components/SystemEventsBadge.jsx`:

```jsx
import { useEffect, useState } from "react";
import { buildAuthHeaders } from "../utils/authz";

export default function SystemEventsBadge() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const res = await fetch(
          "/api/system-events?unresolved_only=true&limit=1",
          { headers: buildAuthHeaders() }
        );
        const data = await res.json();
        setCount(data.count);
      } catch (err) {
        console.error("[SystemEventsBadge]", err);
      }
    };

    fetchCount();
    const interval = setInterval(fetchCount, 30000); // Elke 30s
    return () => clearInterval(interval);
  }, []);

  if (count === 0) return null;

  return (
    <span className="system-events-badge" title={`${count} openstaande platform-issues`}>
      {count}
    </span>
  );
}
```

### 6.2 SystemEventsPanel (standalone pagina of tab)

Maak `web_ui/frontend/src/pages/SystemEventsPage.jsx`:

```jsx
import { useEffect, useState } from "react";
import { buildAuthHeaders } from "../utils/authz";

const SEVERITY_COLORS = {
  info:     "#6B7280",
  warning:  "#D97706",
  error:    "#DC2626",
  critical: "#7C3AED",
};

export default function SystemEventsPage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUnresolvedOnly, setShowUnresolvedOnly] = useState(false);

  const fetchEvents = async () => {
    try {
      const params = showUnresolvedOnly ? "?unresolved_only=true" : "";
      const res = await fetch(`/api/system-events${params}`, {
        headers: buildAuthHeaders(),
      });
      const data = await res.json();
      setEvents(data.events || []);
    } catch (err) {
      console.error("[SystemEventsPage]", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchEvents();
  }, [showUnresolvedOnly]);

  const handleResolve = async (eventId) => {
    await fetch(`/api/system-events/${eventId}/resolve`, {
      method: "PATCH",
      headers: buildAuthHeaders(),
    });
    fetchEvents();
  };

  return (
    <div className="system-events-page">
      <div className="page-header">
        <h1>Platform Events</h1>
        <p className="page-subtitle">
          Operationele fouten van de CEO/orchestrator en het platform.
        </p>
        <label>
          <input
            type="checkbox"
            checked={showUnresolvedOnly}
            onChange={(e) => setShowUnresolvedOnly(e.target.checked)}
          />
          Alleen openstaande
        </label>
      </div>

      {loading && <p>Laden...</p>}

      {!loading && events.length === 0 && (
        <p className="empty-state">Geen platform-events gevonden.</p>
      )}

      <div className="events-list">
        {events.map((event) => (
          <div
            key={event.event_id}
            className={`event-card severity-${event.severity} ${event.resolved ? "resolved" : ""}`}
          >
            <div className="event-header">
              <span
                className="severity-badge"
                style={{ color: SEVERITY_COLORS[event.severity] }}
              >
                {event.severity.toUpperCase()}
              </span>
              <span className="event-type">{event.event_type}</span>
              <span className="event-time">
                {new Date(event.created_at).toLocaleString("nl-NL")}
              </span>
            </div>

            <p className="event-message">{event.message}</p>

            {event.job_id && (
              <a href={`/jobs/${event.job_id}`} className="event-job-link">
                Job bekijken
              </a>
            )}

            {event.agent_id && (
              <span className="event-agent">Agent: {event.agent_id}</span>
            )}

            {!event.resolved && (
              <button
                className="resolve-btn"
                onClick={() => handleResolve(event.event_id)}
              >
                Markeer als opgelost
              </button>
            )}

            {event.resolved && (
              <span className="resolved-label">
                Opgelost op {new Date(event.resolved_at).toLocaleString("nl-NL")}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 6.3 Job-detail view: SystemEvents sectie (Optie C)

Voeg toe aan de bestaande job-detail component (bijv. `JobDetail.jsx`).  
Dit is de lichte Optie C integratie: de job toont zijn eigen events direct.

```jsx
// Voeg toe aan de bestaande JobDetail component

const [jobEvents, setJobEvents] = useState([]);

useEffect(() => {
  if (!job?.id) return;
  fetch(`/api/jobs/${job.id}/system-events`, { headers: buildAuthHeaders() })
    .then((r) => r.json())
    .then((data) => setJobEvents(data.events || []))
    .catch(console.error);
}, [job?.id]);

// Render in de JSX (alleen tonen als er events zijn):
{jobEvents.length > 0 && (
  <div className="job-system-events">
    <h3>Platform Events ({jobEvents.length})</h3>
    {jobEvents.map((evt) => (
      <div key={evt.event_id} className={`job-event severity-${evt.severity}`}>
        <strong>{evt.event_type}</strong>: {evt.message}
        <span className="event-time">
          {new Date(evt.created_at).toLocaleString("nl-NL")}
        </span>
      </div>
    ))}
  </div>
)}
```

---

## 7. NAVIGATIE

Voeg de System Events pagina toe aan de navigatie. Gebruik `SystemEventsBadge` om het aantal openstaande events te tonen.

Zoek de navigatie-component (bijv. `Sidebar.jsx` of `TopHeader.jsx`) en voeg toe:

```jsx
import SystemEventsBadge from "../components/SystemEventsBadge";

// In de nav items:
<NavLink to="/system-events">
  Platform Events <SystemEventsBadge />
</NavLink>
```

Voeg de route toe in de router (bijv. `App.jsx`):

```jsx
import SystemEventsPage from "./pages/SystemEventsPage";

// In de routes:
<Route path="/system-events" element={<SystemEventsPage />} />
```

---

## 8. WAT JE NIET DOET

- Raak `development_points` NIET aan. Die tabel is voor de HR Manager flow.
- Maak geen CEO approval gate voor system_events. De menselijke operator (Timo) lost deze op via de UI.
- Voeg geen `system_events` toe aan het HR wekelijks rapport. Het is een apart platform-monitoring domein.
- Gebruik geen polling onder 30 seconden voor de badge. Platform events zijn niet real-time kritiek.
- Sla geen ruwe stack traces op in `message`. Stack traces horen in `details.traceback`.

---

## 9. ACCEPTATIECRITERIA

Na implementatie moeten alle onderstaande punten aantoonbaar werken:

- [ ] `system_events` tabel bestaat in de database met alle kolommen en indexen
- [ ] `SystemEventsService.log_event()` faalt nooit stilletjes zonder de normale flow te breken
- [ ] CEO-orchestrator logt een event bij: plan-generatie fout, token budget overschrijding, intake loop
- [ ] `GET /api/system-events` geeft events terug, gefilterd op `unresolved_only`
- [ ] `GET /api/jobs/{job_id}/system-events` geeft job-specifieke events terug
- [ ] `PATCH /api/system-events/{event_id}/resolve` markeert een event als opgelost
- [ ] Job-detail view toont events van die job (Optie C)
- [ ] SystemEventsPage toont alle events met severity-kleuren en resolve-knop
- [ ] SystemEventsBadge toont het aantal openstaande events in de navigatie
- [ ] `development_points` tabel en HR flow zijn onaangetast

---

## 10. VERIFICATIE NA IMPLEMENTATIE

```sql
-- Verifieer tabelstructuur
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'system_events'
ORDER BY ordinal_position;

-- Verifieer indexen
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'system_events';

-- Test event aanmaken (handmatig)
INSERT INTO system_events (event_type, severity, message)
VALUES ('system_warning', 'info', 'Test event na migratie')
RETURNING event_id, created_at;

-- Verifieer dat development_points onaangetast is
SELECT COUNT(*) FROM development_points;
```

**Deploy commando (Shelley):**
```bash
git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build && cd ../..
```

---

**Fase-afsluiting:** Meld na elke implementatiefase wat je hebt gedaan en vraag bevestiging voor je verder gaat. Als een verificatiestap faalt, stop dan en rapporteer de fout met de exacte output.
