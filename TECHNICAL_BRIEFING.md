# Wonderz Agentics — Technical Briefing

> Laatste update: 18 feb 2026 — deel dit met elke AI-assistant die aan het project werkt.

## Hosting & Infrastructuur

**Alles draait op één exe.dev VM** — geen Fly.io, geen Render, geen Supabase hosting.

- **VM hostname:** `wonderz-agentic.exe.xyz`
- **OS:** Ubuntu 24.04, persistent disk
- **Repo:** `/home/exedev/wonderz-agentics`
- **GitHub:** `https://github.com/stevenstimo/wonderz-agentics.git`
- **Branch:** `fix/artifact-storage-and-settings` (actief)

## Services (alle op de VM, via systemd)

| Service | Port | Systemd unit | Technologie |
|---------|------|-------------|-------------|
| Frontend | 3000 | `wonderz-frontend` | Vite + React |
| Backend API | 8090 | `wonderz-backend` | FastAPI (uvicorn) |
| Celery Worker | — | `wonderz-worker` | Celery + Redis |
| PostgreSQL | 5432 | `postgresql` | PostgreSQL 16 |
| Redis | 6379 | `redis-server` | Redis |
| Web Terminal | 7681 | `wonderz-terminal` | ttyd |
| Codex Console | 8080 | `wonderz-codex-web` | FastAPI + Codex CLI |

## URLs

| Wat | URL |
|-----|-----|
| Dashboard (default) | `https://wonderz-agentic.exe.xyz/` |
| Frontend | `https://wonderz-agentic.exe.xyz:3000/` |
| Backend API docs | `https://wonderz-agentic.exe.xyz:8090/docs` |
| Codex Console | `https://wonderz-agentic.exe.xyz:8080/` |
| Web Terminal | `https://wonderz-agentic.exe.xyz:7681/` |

## Database

```
DATABASE_URL=postgresql://wonderz:wonderz123@localhost:5432/wonderz
```

**Belangrijke tabellen:**
- `jobs` — job_id, status, context (jsonb), job_type
- `artifacts` — proposed_data (jsonb), original_data (jsonb), artifact_type
- `job_steps` — step_index, agent_name, input_payload (jsonb), output (jsonb)

## Backend Architectuur

**De actieve backend is `app/main.py`** — NIET `web_ui/backend/api_main.py`.

```
app/
  main.py              ← FastAPI app (de echte backend)
  db.py                ← asyncpg pool (init_db_pool / close_db_pool)
  routes/
    jobs.py            ← /api/jobs endpoints (create, list, get, approve-plan, answer)
  orchestration/
    manager.py         ← WorkflowManager: run_workflow, append_artifact, write_job_step
    intake_engine.py   ← Intake vragen generatie
  agents/
    copy_agent.py      ← Tekst generatie agent
    reviewer_agent.py  ← Review agent
```

**`web_ui/backend/api_main.py`** is een oudere SQLAlchemy-based backend met stub endpoints. Wordt NIET gebruikt.

## Frontend Architectuur

```
web_ui/frontend/src/
  main.jsx        ← Routes (/, /dashboard, /jobs/new, /job-center, etc.)
  Dashboard.jsx   ← Hoofddashboard met service health, stats, git info
  JobFlow.jsx     ← Job creatie + workflow (intake → plan → copy → review)
  Sidebar.jsx     ← Navigatie sidebar
  JobCenter.jsx   ← Jobs overzicht
  Settings.jsx    ← API key settings
```

**VITE_API_URL** moet wijzen naar `http://localhost:8090` (of niet gezet, dan fallback).

## Job Workflow

```
Create Job → INTAKE_CLARIFICATION → answer questions
          → PLAN_PROPOSED → approve plan
          → RUNNING → copy_agent → reviewer_agent
          → JOB_READY → review in frontend
```

## Cruciale Fixes (al gedaan)

1. **asyncpg jsonb:** `json.dumps()` nodig voor alle jsonb params (was silent fail)
2. **DB pool import:** `app.routes.jobs` importeert `app.db` als module (niet `_pool` direct)
3. **`init_db_pool()`** leest `DATABASE_URL` at runtime (niet import time)
4. **`user_id`** moet UUID zijn, niet string `'anonymous'`
5. **Artifacts** worden nu correct opgeslagen door `append_artifact()` in manager.py
6. **JOB_READY** status wordt correct gezet wanneer reviewer APPROVED

## API Keys

Opgeslagen in `/home/exedev/.config/wonderz-keys.json`:
- `OPENAI_API_KEY` — voor Codex CLI
- `ANTHROPIC_API_KEY` — voor copy_agent (niet actief, fallback gebruikt)
- `GEMINI_API_KEY` — beschikbaar

## Wat NIET bestaat / NIET gebruikt wordt

- ❌ Fly.io deployment
- ❌ Render deployment  
- ❌ Supabase als database host (alleen auth client-side)
- ❌ `web_ui/backend/api_main.py` als actieve backend
- ❌ Docker containers
- ❌ `/Users/timo/Documents/Claude/` — dat is het Mac-pad, niet relevant voor de VM

## Commando's

```bash
# Services beheren
sudo systemctl restart wonderz-backend
sudo systemctl restart wonderz-frontend
sudo systemctl restart wonderz-worker
journalctl -u wonderz-backend -f  # logs bekijken

# Database
psql postgresql://wonderz:wonderz123@localhost:5432/wonderz

# Status check
curl http://localhost:8090/api/status/summary
```
