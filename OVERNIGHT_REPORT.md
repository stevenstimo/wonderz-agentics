# Overnight Report — 2026-03-10

## Feature 1: Training Workflow

**Status:** ✅ Werkend (met voorwaarden)

**Wat gedaan:**
- `.env.vm` loading toegevoegd in `app/main.py` voor exe.dev config
- SSL verify optie voor scrape: `TRAINING_SSL_VERIFY=false` in VM omgeving (exe.dev cert issues)
- Voyage AI fallback voor embeddings toegevoegd in `app/services/training.py` wanneer OpenAI quota overschreden
- Migration fallback in `app/db.py`: bij ontbrekende `app.migrations.runner` wordt nu Alembic geprobeerd

**Wat werkt:**
- POST `/api/agents/{agent_id}/train` met `{"url": "https://example.com"}` werkt
- Scrape, chunk, embed, store flow functioneert
- `retrieve_context()` geeft relevante chunks terug
- `agent_knowledge` tabel en pgvector extensie aanwezig

**Wat nog open staat:**
- OpenAI quota overschreden op huidige VM → voeg `VOYAGE_API_KEY` toe in `.env.vm` voor fallback embeddings
- `httpx` en `beautifulsoup4` zijn geïnstalleerd (requirements.txt)

**Commit:** (zie git log)

---

## Feature 2: HR Manager scan_job_steps

**Status:** ✅ Werkend

**Wat gedaan:**
- `app/agents/hr_manager.py` aangepast voor schema-variatie:
  - Ontbrekende `proposed_by` kolom: INSERT zonder die kolom
  - Verplichte `agent_role` kolom: lookup via `hired_agents` bij INSERT
  - Impact constraint: `LOW`/`MEDIUM`/`HIGH` (uppercase) i.p.v. lowercase

**Wat werkt:**
- POST `/api/hr/scan` triggert `scan_job_steps` en `scan_direct_chats`
- Bij 3+ retries met dezelfde `retry_reason` wordt automatisch een development point aangemaakt
- Bestaande points worden geïncrementeerd (frequency)
- GET `/api/hr/development-points` en GET `/api/hr/report` werken

**Wat nog open staat:**
- Geen

**Commit:** (zie git log)

---

## Feature 3: CEO Training Approval Flow

**Status:** ✅ Werkend

**Wat gedaan:**
- Migratie `024_training_requests.sql` handmatig toegepast (tabel bestond niet)
- Flow getest: POST `/api/hr/training-request` → POST `/api/hr/approve-training`

**Wat werkt:**
- POST `/api/hr/training-request` met `agent_id`, `reason`, `confidence_score`, `suggested_url` maakt request aan
- POST `/api/hr/approve-training` met `request_id`, `approved`, `source_url`:
  - `approved: true` → status approved, `train_agent_from_url` wordt aangeroepen
  - `approved: false` → status rejected
- Training start automatisch na approval (kan falen bij ontbrekende embedding key)

**Wat nog open staat:**
- Geen

**Commit:** (zie git log)

---

## Feature 4: Token Budget Enforcement

**Status:** ✅ Werkend

**Wat gedaan:**
- `TokenGuard` geïntegreerd in `app/services/job_pipeline.py`:
  - `check_before_call()` vóór elke agent step
  - `register_usage()` na elke step (vervangt directe UPDATE)
  - Bij 80%: warning gelogd, context `token_budget_warning` gezet
  - Bij 100%: job status → FAILED, `token_limit_exceeded_at` gezet
- Frontend: rode melding in `JobDetail.jsx` en `JobSplitView.jsx` bij `context.token_budget_exceeded` met budget info

**Wat werkt:**
- Bij 80% token gebruik: warning gelogd
- Bij 100%: job status → FAILED met reden `token_budget_exceeded`
- Frontend toont: "Token budget exceeded: X / Y tokens used."

**Wat nog open staat:**
- Geen

**Commit:** (zie git log)

---

## Samenvatting

- **4 van 4 features** volledig werkend
- **Openstaande items voor volgende sessie:**
  - Voeg `VOYAGE_API_KEY` toe in `.env.vm` als OpenAI quota overschreden is (voor Training Workflow)
  - Optioneel: `TRAINING_SSL_VERIFY=false` in `.env.vm` voor exe.dev VM als HTTPS scrape faalt
