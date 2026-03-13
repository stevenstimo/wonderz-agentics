# NEXUS Pipeline — Aansluiting en overzicht

## Aangesloten functies en bestanden

| Onderdeel | Bestand | Functie / opmerking |
|-----------|---------|---------------------|
| Agent-aanroep | `app/services/job_pipeline.py` | `_run_step_agent_with_timeout(agent_role, step_name, context, previous_content)` — hergebruikt, niet gekopieerd |
| TokenGuard | `app/services/token_guard.py` | `TokenGuard(db_pool=...).check_before_call()`, `register_usage(job_id, tokens_used, step_id)` |
| Job status | `app/orchestration/nexus_pipeline.py` | `_update_job_status(job_id, status, ctx)` → `UPDATE jobs SET status=..., updated_at=now()` |
| job_steps | `app/orchestration/nexus_pipeline.py` | `_execute_step` → `UPDATE job_steps SET status, output, tokens_used, timing_ms, completed_at` |
| Pool | `app/db.py`, `app/database.py` | `init_db_pool()`, `get_db()` — in `run()`: `pool or await init_db_pool()` |
| Job context merge | `app/orchestration/nexus_pipeline.py` | `_update_job_context(job_id, updates)` → `COALESCE(context,'{}'::jsonb) \|\| $1::jsonb` |

## Assumption-based beslissingen

- **Pool**: `run(job_id, ..., pool=None)` gebruikt meegegeven pool; anders `init_db_pool()`. `init_db_pool()` retourneert de globale pool indien al geïnitialiseerd (`app/db.py`).
- **Agent-signature**: `_run_step_agent_with_timeout` heeft geen `job_id` of `pool`; NEXUS bouwt `context` (o.a. brief, job_post, platform, previous_content) en roept de bestaande functie aan.
- **TokenGuard**: `register_usage(job_id, tokens_used, step_id)` — `step_id` is optioneel; bij ontbreken wordt alleen `jobs.tokens_used` bijgewerkt.
- **job_steps kolommen**: Gebruikt `timing_ms` (niet `latency_ms`); geen aparte `error_log` kolom — fout staat in `output` JSON.
- **Status na phase_2**: In de implementatie zet `phase_2_planning` de status niet op `PLAN_PROPOSED` (zodat RUNNING van approve_plan niet wordt overschreven). `phase_3_execution` houdt RUNNING; phase_6 zet `JOB_READY`. Jobs-tabel heeft `updated_at` (gebruikt in alle UPDATEs).
- **approve-plan met NEXUS**: Bij `USE_NEXUS_PIPELINE=true` wordt `manager.approve_plan(job_id)` vóór `asyncio.create_task(pipeline.run(...))` aangeroepen; daarna start de pipeline op de achtergrond. Het endpoint retourneert direct met status `RUNNING` en message "Plan approved. Workflow started."

## Implementatiebeslissingen

- **approve_plan (Optie A):** In het NEXUS-path roept de jobs-route `manager.approve_plan(job_id)` aan **vóór** `asyncio.create_task(pipeline.run(...))`. Daarmee blijft de audit-step "plan_approved" in `job_steps` behouden en eventuele toekomstige side-effects van approve_plan van toepassing. De status RUNNING wordt door de route al gezet; approve_plan zet die opnieuw (idempotent).
- **Integratietests:** In `tests/test_nexus_integration.py` wordt per test een **eigen** asyncpg-pool aangemaakt (geen `init_db_pool()`), voor event-loopisolatie en om "Event loop is closed" te voorkomen. De LLM wordt gemockt op de definitieplaats: `app.services.job_pipeline._run_step_agent_with_timeout`. De fixture `test_job` / `test_job_with_steps` heeft een assumption-based docstring: `jobs.user_id` heeft in het huidige schema geen FK naar `users`; er wordt een willekeurige UUID gebruikt. Als er later wel een FK komt, moet de fixture worden aangepast (test-user `00000000-0000-0000-0000-000000000001` + INSERT INTO users in setup/teardown).

## Hoe te testen

```bash
pytest tests/test_nexus_pipeline.py -v       # unit tests (geen DB nodig)
pytest tests/test_nexus_integration.py -v   # integratietests (DB vereist)
pytest tests/ -v                             # alles
```

Bij geen bereikbare DB worden de integratietests overgeslagen (skip).

## USE_NEXUS_PIPELINE testen (e2e)

1. **Env**: In `.env` zetten: `USE_NEXUS_PIPELINE=true` (in `.env.example` staat `USE_NEXUS_PIPELINE=false`).
2. **Aanroep**: `POST /api/jobs/{job_id}/approve-plan` (na intake en plan in PLAN_PROPOSED).
3. **Verwacht gedrag**:
   - Response komt direct terug met `status: "RUNNING"` en `message: "Plan approved. Workflow started."`.
   - Pipeline draait op de achtergrond: phase_1 → phase_2 (plan uit DB + eventueel GTM-step) → phase_3 (steps uitvoeren) → phase_4 (QA-loop) → phase_5 (CEO review) → phase_6 (JOB_READY + final_content in context) → phase_7 (alleen log).
   - Job gaat naar `JOB_READY` wanneer de pipeline klaar is; daarna kan de gebruiker via approve-and-deploy naar `COMPLETED` gaan.

**Lokaal draaien** (backend): `./start_backend.sh` of `uvicorn` zoals in de projectdocs; dan een job aanmaken, plan goedkeuren en (met NEXUS aan) direct de RUNNING-response zien en later status/polling tot JOB_READY.

## Openstaande items

- **Error in job_steps**: Fouten worden in `output` (JSON) opgeslagen; als er later een `error_log` kolom op `job_steps` komt, kan NEXUS die vullen voor snellere queries.
