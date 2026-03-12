# Pre-flight Results — Crew Intelligent

**Datum:** 2025-03-12 (sessie)

## 1. Backend bereikbaar
- `curl http://localhost:8090/health`: 404 (endpoint is `/api/health`)
- `curl http://localhost:8090/api/agents`: antwoord (eerste 100 chars) — backend reageert

## 2. Database bereikbaar
- `psql "$DATABASE_URL" -c "SELECT version();"`: OK — PostgreSQL 16.11

## 3. Tabellen op productie/lokaal
- `inbound_emails`: bestaat
- `users`: bestaat
- `hired_agents`: bestaat
- `jobs`: bestaat

## 4. Migration warning
- `python3 -c "import app.migrations; print('OK')"`: OK

## 5. Poort 8000
- `lsof -i :8000`: OK (niets draait op 8000)

## 6. Chunking tests
- `pytest tests/test_training_chunking.py -v`: 3 passed

## Pre-check BLOK 2 (orchestrator)
- Pipeline entry: `run_job_inline` in `app/services/job_pipeline.py`
- Statuswaarden: PLAN_PROPOSED, RUNNING, JOB_READY in `app/services/job_pipeline.py`, `app/routes/jobs.py`, `app/orchestration/manager.py`

## Pre-check BLOK 3 (GTM)
- Uit te voeren: `SELECT agent_id, role FROM hired_agents WHERE role LIKE '%gtm%'` en controle op `app/agents/gtm_specialist.py`

## BLOK 1 — Migraties
- Tabel `inbound_emails` en `users` bestaan al → stap 063 overgeslagen.
- Kolom `jobs.intake_source` bestaat al → stap 064 overgeslagen.

## Supabase trigger
- Bestand `docs/supabase_trigger.sql` aangemaakt; klaar voor operator (Supabase Dashboard → SQL Editor).
