# Overnight rapport 260317 — Latency optimalisatie

## Blok A — Model routing (backend)

### Pre-flight (model-strings)
- **job_pipeline.py:** `CLAUDE_MODEL = DEFAULT_MODEL` (config: `claude-sonnet-4-20250514`); aanroepen op regels 707, 728, 784, 816.
- **intake_engine.py:** `self.model` (uit `DEFAULT_MODEL` via `__init__`), gebruikt in `messages.create` rond regel 334.
- **strategy_room.py:** `self.model` (idem), gebruikt rond regel 232.

### Wijzigingen
- **app/services/job_pipeline.py:** `MODEL_ROUTING` dict toegevoegd; `CLAUDE_MODEL` verwijderd. Copywriter en copywriter_retry → `claude-sonnet-4-6`; reviewer en generic → `claude-haiku-4-5-20251001`. Bij elke stap `[model_routing]` logregel + model doorgeven aan `_log_cache_usage`.
- **app/orchestration/intake_engine.py:** `CEO_MODEL = "claude-sonnet-4-6"` toegevoegd; `__init__` gebruikt `model or CEO_MODEL`. Import `DEFAULT_MODEL` verwijderd.
- **app/orchestration/strategy_room.py:** `CEO_MODEL = "claude-sonnet-4-6"` toegevoegd; `__init__` gebruikt `model or CEO_MODEL`. Import `DEFAULT_MODEL` verwijderd.

### Commit
`19a9fb8` — feat: add model routing — haiku for reviewer/generic, sonnet for CEO/copywriter

---

## Blok B — Observability: model + cache logging

### Wijzigingen
- **app/services/job_pipeline.py:** `_log_cache_usage` uitgebreid met parameter `model`; logt altijd één regel `[llm_usage]` met step, model, input, output, cache_create, cache_read. Alle vier aanroepen geven nu het gebruikte model door.
- **app/orchestration/intake_engine.py:** `[prompt_cache]` vervangen door één `[llm_usage]`-regel (step=intake, model, input/output tokens, cache_create, cache_read).
- **app/orchestration/strategy_room.py:** Idem, step=strategy_room.

### Commit
`11c2b55` — feat: extend llm usage logging with model, input/output tokens and cache fields

---

## Blok C — DB partial index jobs(status)

### Pre-flight
Indexes op `jobs` niet in deze run gecontroleerd (SQL niet uitgevoerd). Migratiebestand alleen aangemaakt; uitvoering door jou via Supabase SQL editor na de overnight run.

### Wijzigingen
- **app/migrations/080_partial_index_jobs.sql** aangemaakt: instructiecomment, `idx_jobs_active` (partial), `idx_agent_runs_job_id`, `idx_agent_runs_created`. CONCURRENTLY; geen transaction wrapper.

### Commit
`f8ad66c` — chore: add migration 080 partial index jobs(status) and agent_runs

---

## Blok D — FastAPI BackgroundTasks audit

### Pre-flight (vindplaatsen)
- jobs.py: BackgroundTasks, add_task op o.a. 247, 519, 621, 719, 759, 864
- clients.py: add_task 1251, 1275, 1344
- hr.py: add_task 635, 1113
- seo_upload.py: add_task 254
- knowledge.py: add_task 159, 223, 424, 657

### Wijzigingen
- **docs/260317_background_tasks_audit.md** aangemaakt: alle add_task-aanroepen, sync/async, duur, aanbeveling, queue-kandidaten.
- **app/routes/jobs.py, clients.py, hr.py, seo_upload.py, knowledge.py:** boven elke add_task die externe API / langlopend werk doet een TODO-comment toegevoegd (migreer naar Celery/ARQ worker).

### Commit
`7265cbc` — chore: audit BackgroundTasks — document queue migration candidates

---

## Blok E — TanStack Query caching (frontend)

### Blocker
TanStack Query is niet geïnstalleerd in de frontend (`web_ui/frontend/package.json` bevat geen `@tanstack/react-query`). Er zijn geen `useQuery`- of `useInfiniteQuery`-aanroepen; data wordt met `fetch` + `useState`/`useEffect` opgehaald. Blok overgeslagen. Optioneel vervolg: eerst @tanstack/react-query toevoegen en data-fetches migreren naar useQuery, daarna staleTime/gcTime toepassen.

### Commit
Geen.

---

## Blok F — Frontend polling cleanup (useRef)

### Wijzigingen
- **web_ui/frontend/src/JobDetail.jsx:** `intervalRef` toegevoegd; polling-effect slaat interval op in `intervalRef.current` en ruimt op in cleanup.
- **web_ui/frontend/src/Dashboard.jsx:** `useRef` geïmporteerd, `timerRef` toegevoegd; idem voor fetchStatus-interval.
- **web_ui/frontend/src/Sidebar.jsx:** `useRef` geïmporteerd, vier refs (inboxIntervalRef, hrIntervalRef, systemEventsIntervalRef, approvalIntervalRef); elk setInterval-effect gebruikt de bijbehorende ref en cleanup.

### Build
`npm run build` geslaagd (tail: built in 12.55s).

### Commit
`e2283ce` — fix: add useRef cleanup to setInterval polling in JobDetail, Dashboard, Sidebar

---

## Samenvatting

### Succesvol afgerond
- **Blok A** — Model routing (Haiku voor reviewer/generic, Sonnet voor CEO/copywriter).
- **Blok B** — LLM usage logging met model, input/output tokens en cache-velden.
- **Blok C** — Migratiebestand 080_partial_index_jobs.sql aangemaakt (SQL niet uitgevoerd; jij draait via Supabase).
- **Blok D** — BackgroundTasks geaudit, audit-doc + TODO-comments bij queue-kandidaten.
- **Blok F** — useRef-cleanup voor setInterval in JobDetail, Dashboard, Sidebar.

### Blocker
- **Blok E** — TanStack Query niet in gebruik; overgeslagen en gedocumenteerd.

### Commit-hashes
| Blok | Hash | Bericht |
|------|------|---------|
| A | 19a9fb8 | feat: add model routing — haiku for reviewer/generic, sonnet for CEO/copywriter |
| B | 11c2b55 | feat: extend llm usage logging with model, input/output tokens and cache fields |
| C | f8ad66c | chore: add migration 080 partial index jobs(status) and agent_runs |
| D | 7265cbc | chore: audit BackgroundTasks — document queue migration candidates |
| E | — | (overgeslagen) |
| F | e2283ce | fix: add useRef cleanup to setInterval polling in JobDetail, Dashboard, Sidebar |

### Bestanden aangeraakt
- app/services/job_pipeline.py
- app/orchestration/intake_engine.py
- app/orchestration/strategy_room.py
- app/migrations/080_partial_index_jobs.sql (nieuw)
- docs/260317_background_tasks_audit.md (nieuw)
- app/routes/jobs.py, clients.py, hr.py, seo_upload.py, knowledge.py
- web_ui/frontend/src/JobDetail.jsx, Dashboard.jsx, Sidebar.jsx
- 260317_overnight_rapport.md (dit bestand)
