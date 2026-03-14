# Client Knowledge Hub — Implementatierapport

**Datum:** 2026-03-14  
**Spec:** docs/cursor_prompt_client_knowledge.md  
**Uitgevoerd:** Fase 1 t/m 6 autonoom.

---

## Beslissingen toegepast

- `SELECT COUNT(*) FROM client_knowledge` was 0 → **DROP TABLE client_knowledge CASCADE** opgenomen bovenaan migration 071.
- Alle FK-referenties **clients(id)** in migration 071 vervangen door **clients(client_id)**.
- **pip install pandas lxml --break-system-packages** uitgevoerd vóór Fase 2C/2D.
- **generate_embedding** overal geïmporteerd uit **app.services.training** (niet training_workflow).

---

## Status per fase

| Fase | Status   | Opmerking |
|------|----------|-----------|
| Fase 1 — Database (migration 071) | **Gedaan** | Migration 071_client_knowledge.sql aangemaakt en uitgevoerd. DROP + client_datasources + client_knowledge + indexen + match_client_knowledge RPC. |
| Fase 2 — Backend extractie (2A–2D) | **Gedaan** | client_crawler.py, client_text_processor.py, client_file_processor.py, client_feed_processor.py. Embedding via app.services.training. |
| Fase 3 — API endpoints | **Gedaan** | POST/GET/DELETE datasources, POST process, POST upload, GET status, GET knowledge in app/routes/clients.py. |
| Fase 4 — CEO context injectie | **Gedaan** | _build_client_knowledge_block in job_pipeline.py; injectie in run_job_inline en run_intake_inline bij @client_slug. |
| Fase 5 — Frontend | **Gedaan** | Tab Kennisbronnen in ClientDetailLayout; ClientKnowledge.jsx met lijst, modal (naam + type + velden), polling, menu (verwerken/verwijderen/upload). |
| Fase 6 — Verificatie | **Gedaan** | Zie verificatie-output hieronder. |

**Blokkades:** Geen.

---

## Verificatie-output Fase 6

### 1. Tabellen aanwezig en leeg

```
=== 1. Tabellen ===
     0
     0

=== 2. Tabellen aanwezig ===
     table_name     
--------------------
 client_datasources
 client_knowledge
(2 rows)
```

### 2. RPC match_client_knowledge

```
 match_client_knowledge
```

### 3. Python-imports (client services)

```
OK: client services import
```

### 4. Handmatige tests (vereisen auth; buiten Cursor)

De volgende commando’s worden op de server / met token uitgevoerd (Shelley):

```bash
# (Shelley) Test website crawl
curl -X POST http://localhost:8090/api/clients/<slug>/datasources \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "Website Asured", "source_type": "website_crawl", "domain": "www.asured.nl"}'

# (Shelley) Process starten
curl -X POST http://localhost:8090/api/clients/<slug>/datasources/<ds_id>/process \
  -H "Authorization: Bearer <token>"

# (Shelley) Status pollen
curl http://localhost:8090/api/clients/<slug>/datasources/<ds_id>/status \
  -H "Authorization: Bearer <token>"
```

Lokaal (in Cursor) uitgevoerd:

```bash
psql "$DATABASE_URL" -f app/migrations/071_client_knowledge.sql
psql "$DATABASE_URL" -c "SELECT table_name FROM information_schema.tables WHERE table_name IN ('client_datasources', 'client_knowledge');"
```

---

## Bestanden gewijzigd/toegevoegd

- **app/migrations/071_client_knowledge.sql** — Migration (DROP + schema + RPC).
- **app/services/client_crawler.py** — Crawl + sitemap.
- **app/services/client_text_processor.py** — Tekst chunken/embedden.
- **app/services/client_file_processor.py** — PDF (pdfplumber) + CSV (pandas).
- **app/services/client_feed_processor.py** — XML product feed.
- **app/routes/clients.py** — Datasource CRUD, process, upload, status, knowledge.
- **app/services/job_pipeline.py** — _build_client_knowledge_block, injectie run_job_inline + run_intake_inline, _load_job met user_id.
- **web_ui/frontend/src/ClientDetailLayout.jsx** — Tab Kennisbronnen.
- **web_ui/frontend/src/ClientKnowledge.jsx** — UI kennisbronnen.
- **web_ui/frontend/src/main.jsx** — Route knowledge, import ClientKnowledge.

---

*Stack: FastAPI + asyncpg + BGE-M3 (app.services.training) + pgvector HNSW.*
