# 260326_CURSOR_clo_agent

## Verplichte git-regels

- Nooit `git restore`, `git checkout --force`, `git reset` of `git clean` uitvoeren
- Bij elke git-operatie eerst `git status` rapporteren en wachten op bevestiging
- Alleen specifieke bestanden stagen, nooit `git add -A`

---

## Context

Wonderz-Agentics, FastAPI + asyncpg backend, React/Vite frontend.

De CLO (Chief Learning Officer) breidt de bestaande HR Manager uit. De HR Manager is de uitvoerende laag. De CLO is de strategische laag daarboven.

**CLO verantwoordelijkheid:**
- Verbeterpunten beheren: van detectie via retry-analyse tot training en verificatie
- Readiness-scores van Newbies bewaken en promoveren of extra training geven
- Skills registreren, koppelen en bewaken per agent via de Skill Factory
- Adviseren over nieuwe agent-types op basis van productie-signalen
- Cross-agent learning coördineren

**Bestaande infrastructuur om op te bouwen:**
- `agent_improvements` tabel — development points per agent
- `newbies` tabel — readiness scores, status, training history
- `agent_knowledge` tabel — training chunks per agent
- HR Manager service in `app/services/hr_manager.py`
- HR Dashboard in `web_ui/frontend/src/HRDashboard.jsx`
- Skill Factory in `web_ui/frontend/src/SkillFactory.jsx`

---

## Pre-flight

```bash
# 1. Check HR Manager service structuur
grep -n "def \|async def " app/services/hr_manager.py | head -20

# 2. Check agent_improvements tabel
grep -rn "agent_improvements" app/routes/hr.py | head -10

# 3. Check bestaande CLO routes
grep -rn "clo\|CLO" app/routes/ --include="*.py" | head -5

# 4. Check Skill Factory route
grep -rn "skill\|Skill" app/routes/ --include="*.py" | grep "router" | head -10

# 5. Check frontend
find web_ui/frontend/src -name "*clo*" -o -name "*CLO*" 2>/dev/null
```

Rapporteer de output. Ga direct door.

---

## Fase 1 — Backend: CLO service

### Nieuw bestand `app/services/clo_service.py`

```python
"""
CLO Service — Chief Learning Officer
Strategische laag boven de HR Manager.
Geen pipeline-impact. Observeren, analyseren, adviseren en coördineren.
"""

import logging
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)


async def get_clo_dashboard(conn: asyncpg.Connection, period_days: int = 30) -> dict:
    """
    Aggregeer leer- en ontwikkeldata voor het CLO dashboard.
    """

    # Development points overzicht
    dev_points = await conn.fetch(
        """
        SELECT
            agent_id,
            COUNT(*) as total_points,
            COUNT(*) FILTER (WHERE status = 'OPEN') as open_points,
            COUNT(*) FILTER (WHERE status = 'RESOLVED') as resolved_points,
            MAX(created_at) as last_point_at
        FROM agent_improvements
        WHERE created_at >= now() - ($1 * interval '1 day')
          AND source != 'hr_blocked_job_notifier'
        GROUP BY agent_id
        ORDER BY open_points DESC
        LIMIT 10
        """,
        period_days,
    )

    # Newbie pipeline status
    newbie_pipeline = await conn.fetch(
        """
        SELECT
            status,
            COUNT(*) as count,
            ROUND(AVG(readiness_score), 1) as avg_readiness
        FROM newbies
        GROUP BY status
        ORDER BY count DESC
        """,
    )

    # Newbies klaar voor promotie (readiness >= 70, status = in_training of ready)
    promotion_ready = await conn.fetch(
        """
        SELECT newbie_id, newbie_name, suggested_role, readiness_score, status
        FROM newbies
        WHERE readiness_score >= 70
          AND status IN ('in_training', 'ready')
        ORDER BY readiness_score DESC
        LIMIT 10
        """,
    )

    # Agents met laagste readiness (training nodig)
    low_readiness_agents = await conn.fetch(
        """
        SELECT
            h.agent_id,
            h.name,
            h.role,
            h.readiness_score,
            COUNT(ai.id) FILTER (WHERE ai.status = 'OPEN') as open_dev_points
        FROM hired_agents h
        LEFT JOIN agent_improvements ai ON ai.agent_id = h.agent_id
        WHERE h.is_active = true
        GROUP BY h.agent_id, h.name, h.role, h.readiness_score
        ORDER BY h.readiness_score ASC NULLS LAST
        LIMIT 10
        """,
    )

    # Training activiteit (laatste 14 dagen)
    training_activity = await conn.fetch(
        """
        SELECT
            DATE(trained_at) as dag,
            COUNT(*) as chunks_added,
            COUNT(DISTINCT agent_id) as agents_trained
        FROM agent_knowledge
        WHERE trained_at >= now() - INTERVAL '14 days'
          AND is_active = true
        GROUP BY DATE(trained_at)
        ORDER BY dag DESC
        """,
    )

    # Cross-training kansen (agents met overlappende kennisgebieden)
    cross_training = await conn.fetch(
        """
        SELECT
            ai.agent_id,
            ai.title,
            ai.description,
            ai.created_at
        FROM agent_improvements ai
        WHERE ai.source = 'hr_manager_scan'
          AND ai.status = 'OPEN'
          AND ai.created_at >= now() - ($1 * interval '1 day')
        ORDER BY ai.created_at DESC
        LIMIT 10
        """,
        period_days,
    )

    return {
        "period_days": period_days,
        "dev_points": [dict(r) for r in dev_points],
        "newbie_pipeline": [dict(r) for r in newbie_pipeline],
        "promotion_ready": [dict(r) for r in promotion_ready],
        "low_readiness_agents": [dict(r) for r in low_readiness_agents],
        "training_activity": [dict(r) for r in training_activity],
        "cross_training": [dict(r) for r in cross_training],
    }


async def get_agent_learning_profile(
    conn: asyncpg.Connection, agent_id: str
) -> dict:
    """
    Gedetailleerd leerprofiel voor één agent.
    """
    agent = await conn.fetchrow(
        "SELECT agent_id, name, role, readiness_score FROM hired_agents WHERE agent_id = $1",
        agent_id,
    )
    if not agent:
        return {}

    dev_points = await conn.fetch(
        """
        SELECT id, title, description, status, created_at, resolved_at
        FROM agent_improvements
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 20
        """,
        agent_id,
    )

    knowledge_sources = await conn.fetch(
        """
        SELECT source_url, title, category, trained_at, chunk_count
        FROM agent_knowledge
        WHERE agent_id = $1 AND is_active = true
        ORDER BY trained_at DESC
        LIMIT 20
        """,
        agent_id,
    )

    return {
        "agent": dict(agent),
        "dev_points": [dict(r) for r in dev_points],
        "knowledge_sources": [dict(r) for r in knowledge_sources],
    }
```

### Nieuw bestand `app/routes/clo.py`

```python
from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.middleware.auth import require_admin_or_super_admin
from app.services.clo_service import get_clo_dashboard, get_agent_learning_profile

router = APIRouter(prefix="/api/clo", tags=["clo"])

@router.get("/dashboard")
async def clo_dashboard(
    period_days: int = Query(default=30, ge=1, le=365),
    _: None = Depends(require_admin_or_super_admin),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_clo_dashboard(conn, period_days=period_days)
    return data

@router.get("/agents/{agent_id}/profile")
async def agent_learning_profile(
    agent_id: str,
    _: None = Depends(require_admin_or_super_admin),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_agent_learning_profile(conn, agent_id)
    return data
```

### Router registreren in `app/main.py`

```python
from app.routes import clo
app.include_router(clo.router)
```

### Verificatie fase 1

```bash
sudo systemctl restart wonderz-backend
curl -s http://localhost:8090/api/clo/dashboard | python3 -m json.tool | head -20
```

Stop en rapporteer. Wacht op bevestiging.

---

## Fase 2 — Frontend: CLO Dashboard pagina

### Nieuw bestand `web_ui/frontend/src/CLODashboard.jsx`

Zes secties:

1. **Overzicht kaarten** — open dev points, agents in training, newbies klaar voor promotie, periode selector.
2. **Newbie pipeline** — statusoverzicht (in_training, ready, hired) met gem. readiness per status.
3. **Klaar voor promotie** — tabel van newbies met readiness >= 70, link naar NewbieDetail.
4. **Agents met meeste open dev points** — tabel, link naar AgentDetail.
5. **Agents met laagste readiness** — tabel gesorteerd op readiness, met aantal open dev points.
6. **Training activiteit** — bar chart via recharts, laatste 14 dagen, chunks per dag.

Gebruik de bestaande Tailwind conventies en stijl van `CFODashboard.jsx` als referentie.

### Route toevoegen

```jsx
const CLODashboard = lazy(() => import('./CLODashboard'));
<Route path="/clo" element={<CLODashboard />} />
```

### Navigatie toevoegen in `Sidebar.jsx`

Voeg "CLO" toe direct onder "CAO" in de Governance sectie.

### Acceptatiecriteria fase 2

- Pagina laadt op `/clo`
- Newbie pipeline statusoverzicht zichtbaar
- Promotie-ready lijst zichtbaar
- Agents met laagste readiness zichtbaar
- `npm run build` slaagt

---

## Wat je NIET doet

- Geen wijzigingen aan HR Manager logica
- Geen nieuwe DB tabellen
- Geen pipeline-aanpassingen
- Geen `git add -A`

---

## Commits na bevestiging

```bash
# Fase 1
git add app/services/clo_service.py app/routes/clo.py app/main.py
git commit -m "feat: CLO service en dashboard endpoint"

# Fase 2
git add web_ui/frontend/src/CLODashboard.jsx web_ui/frontend/src/main.jsx web_ui/frontend/src/Sidebar.jsx
git commit -m "feat: CLO Dashboard pagina met learning en development overzicht"

git push
sudo systemctl restart wonderz-backend
cd web_ui/frontend && npm run build
```
