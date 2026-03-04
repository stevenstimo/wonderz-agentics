# Wonderz-Agentics — Setup & Configuration Lock

> Last verified: 2026-03-03
> Status: ALL ROUTES WORKING

## How to start the backend
```bash
cd ~/wonderz-agentics
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8090
```

## Architecture: Route Registration

Routes are registered in TWO places. Both are required.

### 1. app/routers.py — Central router registry

This file imports all route modules and registers them via `register_routers(app)`.
Each route file defines its OWN prefix internally (e.g. `/api/hr`, `/api/agents`).
Therefore routers.py must NOT add prefix="/api" — just `app.include_router(router)`.

Registered routers:
- agents_router (app/routes/agents.py) → /api/agents
- hr_router (app/routes/hr.py) → /api/hr
- training_router (app/routes/training.py) → /api/training
- crew_router (app/routes/crew.py) → /api/crew
- monitoring_router (app/routes/monitoring.py) → /api/monitoring
- status_router (app/routes/status.py) → /status
- talents_router (app/routes/talents.py) → /api/talents
- skills_router (app/routes/skills.py) → /api/skills
- settings_router (app/routes/settings.py) → /api/settings
- ceo_router (app/routes/ceo.py) → /api/ceo
- explainer_router (app/routes/explainer.py) → /api/explainer
- intelligence_router (app/routes/intelligence.py) → /api/intelligence
- alex_dev_router (app/routes/alex_dev.py) → /api/alex_dev

### 2. app/main.py — App initialization

main.py does two things:
- Creates the FastAPI app
- Calls `register_routers(app)` from app/routers.py
- ALSO includes jobs_router directly (not in routers.py to avoid duplication)

Critical lines in main.py:
```python
app = FastAPI(title="Multi-Agentic Crew - Orchestrator API")

# Register all routes from central registry
from app.routers import register_routers
register_routers(app)

# Jobs router is included separately (was already here before routers.py)
from app.routes.jobs import router as jobs_router
app.include_router(jobs_router)
```

## RULES — Do not break these

1. NEVER add prefix="/api" in routers.py — route files already define their prefix
2. NEVER remove the register_routers(app) call from main.py
3. NEVER add jobs_router to routers.py — it's already in main.py
4. ALWAYS restart uvicorn after code changes (no --reload flag)
5. Route files must use exact database column names — see hired_agents schema below

## Database schemas (verified via psql)

### jobs
id (uuid), user_id (uuid), job_post (text), status (text), source_platform (text),
context (jsonb), created_at (timestamptz), updated_at (timestamptz),
token_budget (int), tokens_used (int), token_limit_exceeded_at (timestamptz),
token_used_total (int)

### job_steps
id (uuid), job_id (uuid), step_index (int), step_name (text), agent_role (text),
unified_tool (text), status (text), input_payload (jsonb), output (jsonb),
tokens_used (int), timing_ms (int), requires_approval (bool),
approved_at (timestamptz), feedback (text), created_at (timestamptz),
started_at (timestamptz), completed_at (timestamptz), token_limit_per_step (int)

### hired_agents
id (uuid), agent_id, name, role, specialization, status, permissions,
system_instructions, knowledge_base_sources, tool_access_whitelist,
hiring_logic, performance_score, completed_tasks, hired_at, updated_at,
is_suspended, system_prompt

### development_points
id, agent_id, agent_role, category, description, impact, status, source_url,
created_at

## Verified working endpoints (2026-03-03)

| Endpoint | Method | Status |
|----------|--------|--------|
| /api/agents | GET | ✅ 200 |
| /api/agents | POST | ✅ 201 |
| /api/agents/{id} | PATCH | ✅ |
| /api/agents/{id} | DELETE | ✅ |
| /api/hr/report | GET | ✅ 200 |
| /api/hr/improvements | GET | ✅ 200 |
| /api/hr/development-points | GET | ✅ |
| /api/hr/scan-patterns | POST | ✅ |
| /api/hr/approve-training | POST | ✅ |
| /api/jobs | POST | ✅ |
| /api/jobs/{id} | GET | ✅ |
| /api/jobs/{id}/answer | PATCH | ✅ |
| /api/jobs/{id}/approve-plan | POST | ✅ |
| /api/jobs/{id}/approve | POST | ✅ |

## Known warnings (non-blocking)

- Migration runner: "No module named 'app.migrations'" at startup — migrations were applied manually via SQL files
- No --reload on uvicorn — restart manually after changes
