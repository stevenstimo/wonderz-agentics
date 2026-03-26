# 260326_CURSOR_coo_cdo_agents

## Verplichte git-regels

- Nooit `git restore`, `git checkout --force`, `git reset` of `git clean` uitvoeren
- Bij elke git-operatie eerst `git status` rapporteren en wachten op bevestiging
- Alleen specifieke bestanden stagen, nooit `git add -A`

---

## Context

Wonderz-Agentics, FastAPI + asyncpg backend, React/Vite frontend.
NEXUS pipeline actief via `app/orchestration/nexus_pipeline.py`.
CEO orchestrator: Donna Paulsen (`agent:personal-assistant:donna`).
COO: Mr. Klein (`agent:ceo:mr-klein`).

**BELANGRIJK:** Dit is de grootste architectuurstap in het C-suite traject.
COO en CDO raken de pipeline. Werk fasen strikt in volgorde.
Bij twijfel over gedrag: stop en rapporteer, ga niet zelfstandig verder.

---

## COO — Chief Operating Officer

**Verantwoordelijkheid:**
- Neemt de RUNNING-fase over van de CEO zodra het plan is goedgekeurd
- Stuurt agents aan per job-stap op basis van het goedgekeurde plan
- Bewaakt voortgang en handelt retries af
- Signaleert kwaliteitsproblemen aan de CLO
- Draagt eindresultaat over aan de CEO voor finale beoordeling

**Huidig gedrag:** Mr. Klein bestaat als agent in `hired_agents` maar heeft geen actieve pipeline-rol. De CEO doet alles zelf via NEXUS.

**Gewenst gedrag:** CEO keurt plan goed → COO neemt RUNNING-fase over → CEO beoordeelt eindresultaat.

---

## CDO — Chief Delivery Officer

**Verantwoordelijkheid:**
- Bewaakt of opgeleverde output echt klopt met wat de klant vroeg
- Haalt periodiek feedback op bij de opdrachtgever
- Vertaalt feedback naar concrete acties bij de juiste C-level
- Signaleert structurele intake-problemen

**Huidig gedrag:** Geen CDO aanwezig.

**Gewenst gedrag:** Na JOB_READY → CDO controleert alignment intake vs output → rapporteert aan CEO.

---

## Pre-flight

```bash
# 1. Check huidige NEXUS pipeline structuur
grep -n "def \|async def \|RUNNING\|CEO\|COO" app/orchestration/nexus_pipeline.py | head -30

# 2. Check hoe CEO review nu werkt
grep -n "_ceo_review\|_run_step\|_execute" app/orchestration/nexus_pipeline.py | head -20

# 3. Check Mr. Klein in hired_agents
# (SQL via Supabase MCP of terminal)
# SELECT agent_id, name, role, is_active FROM hired_agents WHERE name ILIKE '%klein%';

# 4. Check job statussen die COO triggeren
grep -n "RUNNING\|JOB_READY\|status" app/orchestration/nexus_pipeline.py | head -20

# 5. Check of CDO al bestaat
grep -rn "cdo\|CDO\|delivery" app/routes/ --include="*.py" | head -5
```

Rapporteer volledige output. Stop dan. Wacht op bevestiging voor fase 1.

---

## Fase 1 — COO: monitoring dashboard (geen pipeline-impact)

Bouw eerst een COO dashboard dat de RUNNING-fase monitort zonder de pipeline aan te raken. Dit is de veilige eerste stap.

### Nieuw bestand `app/services/coo_service.py`

```python
"""
COO Service — Chief Operating Officer
Fase 1: monitoring en rapportage van de productie-pipeline.
Fase 2 (later): actieve aansturing van de RUNNING-fase.
"""

import logging
import asyncpg

logger = logging.getLogger(__name__)


async def get_coo_dashboard(conn: asyncpg.Connection, period_days: int = 30) -> dict:
    """
    Productie-overzicht voor de COO.
    """

    # Actieve jobs (RUNNING)
    active_jobs = await conn.fetch(
        """
        SELECT id, title, status, created_at, updated_at,
               payload->>'preset_id' as preset_id,
               payload->>'client_name' as client_name
        FROM jobs
        WHERE status = 'RUNNING'
        ORDER BY created_at ASC
        LIMIT 20
        """,
    )

    # Jobs per status laatste periode
    status_breakdown = await conn.fetch(
        """
        SELECT status, COUNT(*) as count,
               ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/60)::numeric, 1) as avg_minutes
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
        GROUP BY status
        ORDER BY count DESC
        """,
        period_days,
    )

    # Stap-performance per agent_role
    step_performance = await conn.fetch(
        """
        SELECT
            js.agent_role,
            COUNT(*) as total_steps,
            COUNT(*) FILTER (WHERE js.status = 'completed') as completed,
            COUNT(*) FILTER (WHERE js.status = 'failed') as failed,
            ROUND(AVG(js.tokens_used)::numeric, 0) as avg_tokens
        FROM job_steps js
        JOIN jobs j ON j.id = js.job_id
        WHERE j.created_at >= now() - ($1 * interval '1 day')
          AND js.agent_role IS NOT NULL
        GROUP BY js.agent_role
        ORDER BY total_steps DESC
        """,
        period_days,
    )

    # Recente retries of fouten
    recent_failures = await conn.fetch(
        """
        SELECT js.job_id, js.step_name, js.agent_role, js.status,
               js.error_message, js.created_at
        FROM job_steps js
        WHERE js.status = 'failed'
          AND js.created_at >= now() - ($1 * interval '1 day')
        ORDER BY js.created_at DESC
        LIMIT 10
        """,
        period_days,
    )

    return {
        "period_days": period_days,
        "active_jobs": [dict(r) for r in active_jobs],
        "status_breakdown": [dict(r) for r in status_breakdown],
        "step_performance": [dict(r) for r in step_performance],
        "recent_failures": [dict(r) for r in recent_failures],
    }
```

### Nieuw bestand `app/routes/coo.py`

```python
from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.middleware.auth import require_admin_or_super_admin
from app.services.coo_service import get_coo_dashboard

router = APIRouter(prefix="/api/coo", tags=["coo"])

@router.get("/dashboard")
async def coo_dashboard(
    period_days: int = Query(default=30, ge=1, le=365),
    _: None = Depends(require_admin_or_super_admin),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_coo_dashboard(conn, period_days=period_days)
    return data
```

### Router in `app/main.py`

```python
from app.routes import coo
app.include_router(coo.router)
```

Stop na fase 1. Rapporteer en wacht op bevestiging.

---

## Fase 2 — CDO: monitoring dashboard

### Nieuw bestand `app/services/cdo_service.py`

```python
"""
CDO Service — Chief Delivery Officer
Bewaakt alignment intake vs output en klanttevredenheid.
Fase 1: monitoring. Fase 2 (later): actieve feedback loop.
"""

import logging
import asyncpg

logger = logging.getLogger(__name__)


async def get_cdo_dashboard(conn: asyncpg.Connection, period_days: int = 30) -> dict:
    """
    Delivery-overzicht voor de CDO.
    """

    # Recente afgeronde jobs (JOB_READY)
    delivered_jobs = await conn.fetch(
        """
        SELECT
            id, title, created_at, updated_at,
            payload->>'preset_id' as preset_id,
            payload->>'client_name' as client_name,
            EXTRACT(EPOCH FROM (updated_at - created_at))/60 as duration_minutes
        FROM jobs
        WHERE status = 'JOB_READY'
          AND created_at >= now() - ($1 * interval '1 day')
        ORDER BY updated_at DESC
        LIMIT 20
        """,
        period_days,
    )

    # Jobs met NEEDS_CHANGES (klant niet tevreden)
    revision_jobs = await conn.fetch(
        """
        SELECT id, title, created_at, updated_at,
               payload->>'client_name' as client_name,
               payload->>'preset_id' as preset_id
        FROM jobs
        WHERE status = 'NEEDS_CHANGES'
          AND created_at >= now() - ($1 * interval '1 day')
        ORDER BY updated_at DESC
        LIMIT 10
        """,
        period_days,
    )

    # Delivery statistieken
    delivery_stats = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'JOB_READY') as delivered,
            COUNT(*) FILTER (WHERE status = 'NEEDS_CHANGES') as revisions,
            COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status = 'JOB_READY') /
                NULLIF(COUNT(*) FILTER (WHERE status IN ('JOB_READY', 'NEEDS_CHANGES', 'FAILED')), 0),
                1
            ) as first_time_right_rate,
            ROUND(AVG(
                EXTRACT(EPOCH FROM (updated_at - created_at))/60
            ) FILTER (WHERE status = 'JOB_READY')::numeric, 1) as avg_delivery_minutes
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
        """,
        period_days,
    )

    # Per client delivery rate
    per_client = await conn.fetch(
        """
        SELECT
            payload->>'client_name' as client_name,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'JOB_READY') as delivered,
            COUNT(*) FILTER (WHERE status = 'NEEDS_CHANGES') as revisions,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status = 'JOB_READY') / NULLIF(COUNT(*), 0), 1
            ) as delivery_rate
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
          AND payload->>'client_name' IS NOT NULL
        GROUP BY payload->>'client_name'
        ORDER BY total DESC
        LIMIT 10
        """,
        period_days,
    )

    return {
        "period_days": period_days,
        "delivery_stats": dict(delivery_stats) if delivery_stats else {},
        "delivered_jobs": [dict(r) for r in delivered_jobs],
        "revision_jobs": [dict(r) for r in revision_jobs],
        "per_client": [dict(r) for r in per_client],
    }
```

### Nieuw bestand `app/routes/cdo.py`

```python
from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.middleware.auth import require_admin_or_super_admin
from app.services.cdo_service import get_cdo_dashboard

router = APIRouter(prefix="/api/cdo", tags=["cdo"])

@router.get("/dashboard")
async def cdo_dashboard(
    period_days: int = Query(default=30, ge=1, le=365),
    _: None = Depends(require_admin_or_super_admin),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_cdo_dashboard(conn, period_days=period_days)
    return data
```

### Router in `app/main.py`

```python
from app.routes import cdo
app.include_router(cdo.router)
```

Stop na fase 2. Rapporteer en wacht op bevestiging.

---

## Fase 3 — Frontend: COO en CDO Dashboard pagina's

### `web_ui/frontend/src/COODashboard.jsx`

Vier secties:
1. **Actieve jobs** — lijst van RUNNING jobs met preset en client naam
2. **Status breakdown** — tabel per status met gem. doorlooptijd
3. **Stap performance per rol** — tabel agent_role, completed, failed, avg tokens
4. **Recente fouten** — lijst van mislukte job_steps

### `web_ui/frontend/src/CDODashboard.jsx`

Vier secties:
1. **Delivery kaarten** — delivered, revisions, failed, first-time-right rate %, gem. doorlooptijd
2. **Per client delivery rate** — tabel gesorteerd op totaal
3. **Recente leveringen** — lijst van JOB_READY jobs
4. **Jobs in revisie** — lijst van NEEDS_CHANGES jobs

### Routes toevoegen

```jsx
const COODashboard = lazy(() => import('./COODashboard'));
const CDODashboard = lazy(() => import('./CDODashboard'));
<Route path="/coo" element={<COODashboard />} />
<Route path="/cdo" element={<CDODashboard />} />
```

### Navigatie in `Sidebar.jsx`

Voeg toe onder Governance:
- "COO" direct onder "CLO"
- "CDO" direct onder "COO"

### Acceptatiecriteria fase 3

- `/coo` laadt met actieve jobs overzicht
- `/cdo` laadt met delivery stats
- Beide periode selectors werken
- `npm run build` slaagt

---

## Wat je NIET doet

- Geen wijzigingen aan `nexus_pipeline.py` — COO pipeline-integratie is een apart traject
- Geen nieuwe DB tabellen
- Geen `git add -A`

---

## Commits na bevestiging per fase

```bash
# Fase 1
git add app/services/coo_service.py app/routes/coo.py app/main.py
git commit -m "feat: COO service en dashboard endpoint"

# Fase 2
git add app/services/cdo_service.py app/routes/cdo.py app/main.py
git commit -m "feat: CDO service en dashboard endpoint"

# Fase 3
git add web_ui/frontend/src/COODashboard.jsx web_ui/frontend/src/CDODashboard.jsx web_ui/frontend/src/main.jsx web_ui/frontend/src/Sidebar.jsx
git commit -m "feat: COO en CDO Dashboard pagina's"

git push
sudo systemctl restart wonderz-backend
cd web_ui/frontend && npm run build
```
