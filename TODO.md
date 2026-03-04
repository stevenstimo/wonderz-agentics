# Wonderz-Agentics — TODO & Status Tracker

> Last updated: 2026-03-04
> Note: All database schemas verified via psql on 2026-03-04

---

## Status: Database & Migrations

| Migration | Status | Notes |
|-----------|--------|-------|
| 007_hired_agents.sql | ✅ Done | hired_agents + agent_knowledge + ivfflat index |
| 008_jobs.sql | ✅ Done | jobs + job_steps met token tracking |
| 009_development_points.sql | ✅ Done | development_points met impact/status checks |

---

## Status: Backend Routes (app/routes/)

| Route | Endpoint | Status | Notes |
|-------|----------|--------|-------|
| agents.py | GET /api/agents | ✅ Done | Kolomnamen aligned met hired_agents schema |
| agents.py | POST /api/agents | ✅ Done | CRUD compleet |
| agents.py | PATCH /api/agents/{id} | ✅ Done | Partial update |
| agents.py | DELETE /api/agents/{id} | ✅ Done | |
| jobs.py | /api/jobs/* | ✅ Done | POST /api/jobs, GET /api/jobs/{id}, PATCH, approve, feedback all registered |
| governance.py | /api/governance/* | ⚠️ Code klaar | Niet getest tegen live DB |
| training.py | /api/hr/approve-training | ⚠️ Code klaar | Niet getest tegen live DB |
| hr.py | /api/hr/* | ✅ Done | all sub-endpoints working: /report, /improvements, /development-points, etc. |

---

## Status: Platform Spec v1.4

Volledig afgerond — 14/14 fasen, 52 tests groen.

---

## Status: Product Spec v1.2

| Fase | Omschrijving | Status |
|------|-------------|--------|
| P01 | 007_hired_agents.sql | ✅ Done |
| P02 | 008_jobs.sql | ✅ Done |
| P03 | 009_development_points.sql | ✅ Done |
| P04 | NewCrewMember + agents endpoint | ✅ Done (gefixt) |
| P05 | IntakeEngine | ⚠️ Code klaar, niet gekoppeld |
| P06 | StrategyRoom | ⚠️ Code klaar, niet gekoppeld |
| P07 | Job state machine | ⚠️ Code klaar, niet gekoppeld |
| P08 | UnifiedToolBridge + adapters | ⚠️ Code klaar, niet gekoppeld |
| P09 | TrainingWorkflow | ⚠️ Code klaar, niet getest |
| P10 | CEO approval training | ⚠️ Code klaar, niet getest |
| P11 | HR scan + development points | ⚠️ Code klaar, niet getest |
| P12 | HR weekrapport + API | ⚠️ Code klaar, niet getest |
| P13 | IntakeChat + realtime hook | ⚠️ Frontend gebouwd, niet verbonden |
| P14 | PlanViewer | ⚠️ Frontend gebouwd, niet verbonden |
| P15 | LiveTracker | ⚠️ Frontend gebouwd, niet verbonden |
| P16 | ReviewDiff | ⚠️ Frontend gebouwd, niet verbonden |
| P17 | Product API endpoints | ⚠️ Code klaar, niet getest |
| P18 | A/B validatie | ⚠️ Code klaar, niet getest |
| P19 | Cross-agent learning | ⚠️ Code klaar, niet getest |
| P20 | Training priority/offline | ⚠️ Code klaar, niet getest |

---

## TODO: Hoge Prioriteit

- [x] Alle routes testen tegen live DB — agents.py was stuk door verkeerde kolomnamen. Dezelfde check nodig voor jobs.py, governance.py, training.py, hr.py ✅ Done
- [x] get_db() centraliseren — staat nu als placeholder per route, moet 1x gedefinieerd in app/database.py ✅ Done
- [x] workers/tasks.py — TODO: log to job_steps table with status='failed' in run_intake ✅ Done
- [x] workers/tasks.py — TODO: log to job_steps with status='failed' in run_job ✅ Done
- [x] jobs.py fix — kolomnamen aligned met live DB ✅ Done
- [ ] IntakeEngine (P05) koppelen — flow testen met echte data door de hele pipeline

## TODO: Medium Prioriteit

- [ ] Frontend → backend koppeling — P13-P16 componenten verbinden met draaiende API
- [ ] Job state machine (P07) — end-to-end flow testen: intake → strategy → execution → review
- [ ] TrainingWorkflow testen — P09-P12 tegen live DB valideren
- [ ] Error handling audit — alle routes checken op correcte HTTP status codes en foutmeldingen

## TODO: Lage Prioriteit

- [ ] A/B validatie (P18) — integratie testen
- [ ] Cross-agent learning (P19) — integratie testen
- [ ] Training priority/offline (P20) — integratie testen
- [ ] Test suite uitbreiden — coverage voor nieuwe CRUD endpoints
- [ ] API documentatie — OpenAPI/Swagger docs genereren en valideren

---

## Technische Schuld

- get_db() placeholder in meerdere route files → centraliseren ✅ Done
- Pydantic fallbacks voor omgevingen zonder packages → opruimen als packages definitief zijn
- Frontend gebruikt dummy data op veel plekken → vervangen door live API calls
- Geen CI/CD pipeline → overwegen voor automatische tests bij commit
- Migration runner missing: app.migrations module not found at startup (non-blocking warning)
- Backend runs without --reload flag, manual restart needed after code changes

---

## Conventies

- ✅ Done = werkt op productie, getest
- ⚠️ Code klaar = opgeleverd door Codex, niet gevalideerd tegen live omgeving
- ❌ Stuk = bekend broken, moet gefixt
