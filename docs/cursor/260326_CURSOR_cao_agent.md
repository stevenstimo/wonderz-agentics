# 260326_CURSOR_cao_agent

## Verplichte git-regels

- Nooit `git restore`, `git checkout --force`, `git reset` of `git clean` uitvoeren
- Bij elke git-operatie eerst `git status` rapporteren en wachten op bevestiging
- Alleen specifieke bestanden stagen, nooit `git add -A`

---

## Context

Wonderz-Agentics, FastAPI + asyncpg backend, React/Vite frontend.
De CAO is een monitoring-only C-level rol. Geen pipeline-impact, geen orchestratie.

**CAO verantwoordelijkheid:**
- Job-uitkomsten analyseren: approval-rates, retry-rates, doorlooptijden
- Prestaties vergelijken per agent-combinatie en per klant-type
- Structurele patronen signaleren die niet zichtbaar zijn in individuele jobs
- Rapportages opstellen voor de CEO over crew-brede trends
- Advies geven aan COO (welke workflows slecht presteren) en CLO (welke trainingen effect hebben)

**Data beschikbaar in bestaande tabellen:**
- `jobs`: status, created_at, updated_at, client_id, preset_id, payload
- `job_steps`: step_name, agent_id, agent_role, status, tokens_used
- `hired_agents`: agent_id, name, role, readiness_score
- `token_usage_log`: kosten per stap (net gebouwd door CFO)

---

## Pre-flight

```bash
# 1. Check bestaande job statussen
grep -rn "JOB_READY\|APPROVED\|FAILED\|BLOCKED\|NEEDS_CHANGES" app/orchestration/ --include="*.py" | head -10

# 2. Check job_steps kolommen
grep -n "status\|retry\|agent_id\|agent_role" app/routes/jobs.py | head -20

# 3. Check of er al een CAO route bestaat
grep -rn "cao\|CAO" app/routes/ --include="*.py" | head -5

# 4. Check frontend
find web_ui/frontend/src -name "*cao*" -o -name "*CAO*" 2>/dev/null
```

Rapporteer de output. Ga direct door naar fase 1.

---

## Fase 1 — Backend: CAO service + endpoint

### Nieuw bestand `app/services/cao_service.py`

```python
"""
CAO Service — Crew Analytics & Performance Monitoring
Geen pipeline-impact. Alleen observeren, analyseren en rapporteren.
"""

import logging
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)


async def get_cao_dashboard(
    conn: asyncpg.Connection,
    period_days: int = 30,
) -> dict:
    """
    Aggregeer performance-inzichten voor het CAO dashboard.
    """

    # Overall job statistieken
    job_stats = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total_jobs,
            COUNT(*) FILTER (WHERE status = 'JOB_READY') as completed,
            COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
            COUNT(*) FILTER (WHERE status = 'BLOCKED') as blocked,
            COUNT(*) FILTER (WHERE status = 'NEEDS_CHANGES') as needs_changes,
            ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/60)::numeric, 1) as avg_duration_minutes
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
        """,
        period_days,
    )

    # Approval rate per preset
    per_preset = await conn.fetch(
        """
        SELECT
            COALESCE(payload->>'preset_id', 'geen preset') as preset,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'JOB_READY') as completed,
            COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
            COUNT(*) FILTER (WHERE status = 'BLOCKED') as blocked,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status = 'JOB_READY') / NULLIF(COUNT(*), 0), 1
            ) as approval_rate
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
        GROUP BY payload->>'preset_id'
        ORDER BY total DESC
        LIMIT 10
        """,
        period_days,
    )

    # Performance per agent
    per_agent = await conn.fetch(
        """
        SELECT
            js.agent_id,
            js.agent_role,
            COUNT(*) as total_steps,
            COUNT(*) FILTER (WHERE js.status = 'completed') as completed_steps,
            COUNT(*) FILTER (WHERE js.status = 'failed') as failed_steps,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE js.status = 'completed') / NULLIF(COUNT(*), 0), 1
            ) as success_rate
        FROM job_steps js
        JOIN jobs j ON j.id = js.job_id
        WHERE j.created_at >= now() - ($1 * interval '1 day')
          AND js.agent_id IS NOT NULL
        GROUP BY js.agent_id, js.agent_role
        ORDER BY total_steps DESC
        LIMIT 10
        """,
        period_days,
    )

    # Dagelijkse trend (laatste 14 dagen)
    daily_trend = await conn.fetch(
        """
        SELECT
            DATE(created_at) as dag,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'JOB_READY') as completed,
            COUNT(*) FILTER (WHERE status = 'FAILED') as failed
        FROM jobs
        WHERE created_at >= now() - INTERVAL '14 days'
        GROUP BY DATE(created_at)
        ORDER BY dag DESC
        """,
    )

    # Meest geblokkeerde rollen
    blocked_roles = await conn.fetch(
        """
        SELECT
            details->>'missing_role_key' as role_key,
            details->>'missing_role_label' as role_label,
            COUNT(*) as blocked_count
        FROM agent_improvements
        WHERE source = 'hr_blocked_job_notifier'
          AND status = 'OPEN'
          AND created_at >= now() - ($1 * interval '1 day')
        GROUP BY details->>'missing_role_key', details->>'missing_role_label'
        ORDER BY blocked_count DESC
        LIMIT 5
        """,
        period_days,
    )

    return {
        "period_days": period_days,
        "job_stats": dict(job_stats) if job_stats else {},
        "per_preset": [dict(r) for r in per_preset],
        "per_agent": [dict(r) for r in per_agent],
        "daily_trend": [dict(r) for r in daily_trend],
        "blocked_roles": [dict(r) for r in blocked_roles],
    }
```

### Nieuw bestand `app/routes/cao.py`

```python
from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.middleware.auth import require_admin_or_super_admin
from app.services.cao_service import get_cao_dashboard

router = APIRouter(prefix="/api/cao", tags=["cao"])

@router.get("/dashboard")
async def cao_dashboard(
    period_days: int = Query(default=30, ge=1, le=365),
    _: None = Depends(require_admin_or_super_admin),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_cao_dashboard(conn, period_days=period_days)
    return data
```

### Router registreren in `app/main.py`

```python
from app.routes import cao
app.include_router(cao.router)
```

### Verificatie fase 1

```bash
sudo systemctl restart wonderz-backend
curl -s http://localhost:8090/api/cao/dashboard | python3 -m json.tool | head -20
```

Stop en rapporteer. Wacht op bevestiging.

---

## Fase 2 — Frontend: CAO Dashboard pagina

### Nieuw bestand `web_ui/frontend/src/CAODashboard.jsx`

Vier secties:

1. **Overzicht kaarten** — totale jobs, completion rate, failed rate, geblokkeerde jobs, gem. doorlooptijd. Periode selector (7/30/90 dagen).
2. **Performance per preset** — tabel met preset naam, totaal, completed, failed, approval rate %.
3. **Performance per agent** — tabel met agent_id, rol, total steps, success rate %.
4. **Dagelijkse trend** — bar chart via recharts (al geïnstalleerd), 14 dagen, completed vs failed.

Gebruik de bestaande Tailwind conventies en stijl van `CFODashboard.jsx` als referentie.

### Route toevoegen

```jsx
const CAODashboard = lazy(() => import('./CAODashboard'));
<Route path="/cao" element={<CAODashboard />} />
```

### Navigatie toevoegen in `Sidebar.jsx`

Voeg "CAO" toe direct onder "CFO" in de Governance sectie.

### Acceptatiecriteria fase 2

- Pagina laadt op `/cao`
- Overzichtskaarten tonen job statistieken
- Tabel per preset met approval rate
- Periode selector werkt
- `npm run build` slaagt

---

## Wat je NIET doet

- Geen pipeline-logica aanpassen
- Geen nieuwe tabellen aanmaken (CAO gebruikt bestaande data)
- Geen `git add -A`

---

## Commits na bevestiging

```bash
# Fase 1
git add app/services/cao_service.py app/routes/cao.py app/main.py
git commit -m "feat: CAO service en dashboard endpoint"

# Fase 2
git add web_ui/frontend/src/CAODashboard.jsx web_ui/frontend/src/main.jsx web_ui/frontend/src/Sidebar.jsx
git commit -m "feat: CAO Dashboard pagina met crew performance analytics"

git push
sudo systemctl restart wonderz-backend
cd web_ui/frontend && npm run build
```
