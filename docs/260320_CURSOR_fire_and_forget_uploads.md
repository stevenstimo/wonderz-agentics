**Uitvoeringsregels (altijd van toepassing)**

1. **ARQ worker:** De service heet `wonderz-worker`, niet `crew-worker`.
   - Herstart: `sudo systemctl restart wonderz-worker`
   - Logs: `journalctl -u wonderz-worker` (niet `crew-worker`)

2. **Git:** Nooit `git restore`, `git checkout --force`, `git reset` of `git clean` uitvoeren.
   Bij elke git-operatie eerst `git status` rapporteren en wachten op bevestiging.
   Nooit `git add -A`.

3. **Knowledge / Fase 2:** De kennis-upload flow is al deels gebouwd via `run_embedding_task` in `app/worker.py` (onder meer in `WorkerSettings.functions`). Controleer eerst of die taken al bestaan en hoe ze aangeroepen worden voordat je parallel nieuwe, overlappende ARQ-taken definieert — liever uitbreiden of hergebruiken dan dupliceren.

---

# 260320 — Crew Intelligent: Fire-and-Forget Uploads

**Versie:** 1.0  
**Datum:** 20 maart 2026  
**Status:** Klaar voor uitvoering  
**Doel:** Alle forms die nu een synchrone, lang-lopende request doen worden omgebouwd naar het fire-and-forget patroon: frontend krijgt direct een `pending` record + ID terug, ARQ worker verwerkt op de achtergrond.

---

## Context

De ARQ worker is live (`wonderz-worker.service`). Jobs draaien server-side door, ook als de browser dicht is. Dit patroon moet nu ook gelden voor alle andere zware operaties: uploads, crawls, training, SEO.

**Het probleem dat dit oplost:**

Meerdere forms blokkeren de browser momenteel totdat de server klaar is. Voor een knowledge upload of een client datasource crawl kan dit tientallen seconden zijn. Als de user wegnavigateert of de verbinding valt, gaat de operatie verloren. Er is geen status-tracking, geen recovery, geen feedback.

**Het patroon dat overal geldt na deze implementatie:**

```
1. Frontend stuurt form in (POST)
2. Backend valideert de input (sync, <100ms)
3. Backend maakt direct een record aan met status `pending` + geeft ID terug
4. Backend enqueut een ARQ taak met dat record-ID
5. Browser is vrij — navigeer weg, sluit laptop
6. ARQ worker pikt de taak op, verwerkt, update status naar `processing` → `completed` / `failed`
7. Frontend polt de status via bestaand polling-mechanisme en toont de bijgewerkte staat
```

**Scope van deze implementatie:**

| Form / operatie | Huidig gedrag | Na implementatie |
|---|---|---|
| Knowledge upload (URL + bestand) | Sync: blokkeert tot crawl + embed klaar | Pending record → ARQ worker crawlt + embeddt |
| Client datasource crawl | Sync: blokkeert tot crawl klaar | Pending record → ARQ worker crawlt |
| Agent training (URL) | Sync: blokkeert tot embed klaar | Pending record → ARQ worker embeddt |
| SEO keyword job | Sync: blokkeert tot GSC-fetch + analyse | Pending record → ARQ worker fetcht + analyseert |

---

## Pre-flight audit — verplicht vóór elke code

Voer alle checks uit en rapporteer de output per stap. Stop bij een onverwacht resultaat en meld het.

```bash
# (terminal) 1. ARQ worker draait?
systemctl is-active wonderz-worker
# verwacht: active

# (terminal) 2. Redis bereikbaar?
redis-cli ping
# verwacht: PONG

# (terminal) 3. Vind alle routes die sync zware operaties doen
# (URL-fetch, embed, crawl, externe API-calls)
grep -rn "httpx\|requests\|BeautifulSoup\|embed\|crawl\|generate_embeddings\|asyncio.sleep\|gsc\|search_console" \
  app/routers/ app/routes/ --include="*.py" -l
# Noteer elk bestand

# (terminal) 4. Vind alle BackgroundTasks die nog niet naar ARQ zijn gemigreerd
grep -rn "BackgroundTasks\|add_task" app/routers/ app/routes/ --include="*.py"
# Als hier resultaten uitkomen: die horen ook in deze migratie

# (terminal) 5. Controleer welke tabellen status-kolommen hebben die relevant zijn
grep -rn "status.*pending\|status.*processing\|status.*failed\|status.*completed" \
  app/ --include="*.py" | grep -v "jobs\b" | head -30
# Doel: begrijpen welke tabellen al een status-lifecycle hebben
```

```sql
-- (SQL) 6. Overzicht status-kolommen in relevante tabellen
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name = 'status'
  AND table_name IN (
    'knowledge_docs', 'knowledge_sources', 'newbie_library',
    'client_datasources', 'agent_knowledge', 'seo_jobs',
    'training_requests', 'hired_agents'
  )
ORDER BY table_name;

-- (SQL) 7. Bestaat er al een async_tasks of background_tasks tabel?
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name ILIKE '%task%'
  OR table_name ILIKE '%queue%'
  OR table_name ILIKE '%job%'
ORDER BY table_name;
```

Rapporteer de volledige output van stappen 1 t/m 7 vóór je aan Fase 1 begint.

---

## Architectuurbeslissing — status per domein vs. centrale task-tabel

Kies op basis van de pre-flight uitkomst één van twee aanpakken en communiceer de keuze:

**Aanpak A — Status op het domein-record zelf** *(voorkeur als de tabel al een `status`-kolom heeft)*  
Knowledge-record krijgt `status = 'pending'`, ARQ worker update naar `processing` → `completed`. Frontend polt `GET /api/knowledge/{id}` en leest de status direct van het record.

**Aanpak B — Centrale `async_tasks` tabel** *(voorkeur als meerdere domein-tabellen geen status-kolom hebben)*  
Eén tabel bijhoudt alle achtergrond-taken: `task_id`, `task_type`, `entity_id`, `status`, `error`. Frontend polt `GET /api/tasks/{task_id}`.

**Beslissingsregel:**
- Als ≥ 2 van de 4 betrokken domein-tabellen al een `status`-kolom hebben → Aanpak A, voeg `status` toe aan tabellen die het nog missen.
- Als geen enkele domein-tabel een `status`-kolom heeft → Aanpak B, maak centrale `async_tasks` tabel.
- Nooit beide tegelijkertijd. Consistentie is het doel.

Documenteer de keuze bovenaan elk bestand dat je aanmaakt: `# Pattern: fire-and-forget / Aanpak A`.

---

## Fasering

- **Fase 1** eerst, daarna **Fasen 2–5** (kunnen in één lange sessie **parallel** door verschillende agents of streams).
- **Fase 6 start pas** als **alle vier** domeinen (2–5) af zijn — geen smoke test als er nog een deelflow ontbreekt.
- Optioneel: na elke afgeronde fase kort rapporteren; bij parallel werk één moment van “2–5 compleet” vóór Fase 6.

| Fase | Beschrijving | Type |
|------|-------------|------|
| 1 | Schema updates + ARQ taakdefinities | Backend |
| 2 | Knowledge upload omgebouwd | Backend + Frontend |
| 3 | Client datasource crawl omgebouwd | Backend + Frontend |
| 4 | Agent training omgebouwd | Backend + Frontend |
| 5 | SEO job omgebouwd | Backend + Frontend |
| 6 | Smoke test alle vier flows | Verificatie |

---

## Fase 1 — Schema updates + ARQ taakdefinities

### 1.1 Schema

Pas op basis van de pre-flight-uitkomst en de architectuurbeslissing (A of B) de benodigde tabellen aan.

**Als Aanpak A:** voeg `status` toe aan elke domein-tabel die het mist:

```sql
-- Voorbeeld voor knowledge_docs (pas tabelnamen aan op basis van pre-flight)
ALTER TABLE knowledge_docs
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS error_message TEXT,
  ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- Zelfde patroon voor client_datasources, indien van toepassing
-- Zelfde patroon voor seo_jobs, indien van toepassing
```

**Als Aanpak B:** maak de centrale tabel:

```sql
CREATE TABLE IF NOT EXISTS async_tasks (
  task_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type     TEXT NOT NULL,          -- 'knowledge_upload', 'datasource_crawl', 'agent_training', 'seo_job'
  entity_id     TEXT NOT NULL,          -- ID van het domein-record
  entity_table  TEXT NOT NULL,          -- naam van de domein-tabel
  status        TEXT NOT NULL DEFAULT 'pending',  -- pending | processing | completed | failed
  error_message TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  started_at    TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_async_tasks_entity ON async_tasks(entity_table, entity_id);
CREATE INDEX IF NOT EXISTS idx_async_tasks_status ON async_tasks(status);
```

Voeg de migratie toe als `app/migrations/XXX_fire_and_forget_status.sql` met het juiste volgnummer.

### 1.2 ARQ taakdefinities toevoegen aan `app/worker.py`

Voeg de vier nieuwe taken toe aan de bestaande `app/worker.py`. Voeg ze toe aan de `functions`-lijst in `WorkerSettings`.

**Knowledge-upload:** voordat je hier een aparte `process_knowledge_upload`-achtige taak toevoegt, doorzoek `app/worker.py` op `run_embedding_task` en de enqueue-kant in de knowledge-routes. Als die pipeline al de upload/embed afhandelt, geen tweede identieke taak toevoegen — uitbreiden of de bestaande naam enqueue-en.

**Taaksjabloon (gebruik dit voor alle vier):**

```python
async def process_knowledge_upload(ctx: dict, record_id: str) -> dict:
    """
    Verwerkt een knowledge upload op de achtergrond.
    Vervangt de synchrone crawl + embed in de knowledge router.
    
    ctx bevat: db_pool (asyncpg pool, aangemaakt in startup)
    """
    from app.services.knowledge_service import crawl_and_embed  # pas import aan
    
    logger.info(f"[ARQ] knowledge_upload gestart: {record_id}")
    db_pool = ctx["db_pool"]
    
    # Markeer als processing
    await _set_task_status(db_pool, "knowledge_docs", record_id, "processing")
    
    try:
        await crawl_and_embed(db_pool=db_pool, record_id=record_id)
        await _set_task_status(db_pool, "knowledge_docs", record_id, "completed")
        logger.info(f"[ARQ] knowledge_upload voltooid: {record_id}")
        return {"record_id": record_id, "status": "completed"}
    except Exception as e:
        logger.exception(f"[ARQ] knowledge_upload gefaald: {record_id} — {e}")
        await _set_task_status(db_pool, "knowledge_docs", record_id, "failed", error=str(e))
        raise


async def _set_task_status(
    db_pool, table: str, record_id: str, status: str, error: str | None = None
) -> None:
    """
    Update de status op het domein-record (Aanpak A)
    of in de async_tasks tabel (Aanpak B).
    Pas dit aan op basis van de architectuurbeslissing.
    """
    # Aanpak A: update het domein-record direct
    now = "now()"
    async with db_pool.acquire() as conn:
        if status == "processing":
            await conn.execute(
                f"UPDATE {table} SET status=$1, started_at=now() WHERE id=$2::uuid",
                status, record_id,
            )
        elif status in ("completed", "failed"):
            await conn.execute(
                f"""UPDATE {table}
                    SET status=$1, completed_at=now(), error_message=$2
                    WHERE id=$3::uuid""",
                status, error, record_id,
            )
        else:
            await conn.execute(
                f"UPDATE {table} SET status=$1 WHERE id=$2::uuid",
                status, record_id,
            )
```

Maak analoge taken aan voor:
- `process_datasource_crawl(ctx, record_id)`
- `process_agent_training(ctx, record_id)`
- `process_seo_job(ctx, record_id)`

Voeg alle vier toe aan `WorkerSettings.functions`.

**Fase 1 gereed als:** Migratie is uitgevoerd (verifieer via SQL), `app/worker.py` bevat de vier nieuwe taken, worker herstart zonder errors.

---

## Fase 2 — Knowledge upload omgebouwd

**Eerst in de code:** `app/worker.py` bevat al `run_embedding_task` (en gerelateerde embedding-flow); `app/services/knowledge_upload_service.py` bevat de echte implementatie. Pas routes en worker aan op basis van wat er al staat — geen dubbele ARQ-job voor hetzelfde document.

### 2.1 Backend: `POST /api/knowledge` (of equivalent)

Vervang de synchrone verwerking door het fire-and-forget patroon.

**Vóór (huidig patroon — verwijder dit):**
```python
@router.post("/knowledge")
async def create_knowledge(payload: KnowledgeCreate, db=Depends(get_db)):
    record = await db.fetchrow("INSERT INTO knowledge_docs ... RETURNING *")
    await crawl_and_embed(record["id"])  # ← blokkeert de response
    return {"id": record["id"], "status": "completed"}
```

**Na (fire-and-forget):**
```python
@router.post("/knowledge", status_code=202)
async def create_knowledge(
    payload: KnowledgeCreate,
    db=Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    # 1. Valideer input (sync, goedkoop)
    # 2. Maak record aan met status 'pending'
    record = await db.fetchrow(
        """INSERT INTO knowledge_docs (source_url, agent_id, status, created_at)
           VALUES ($1, $2, 'pending', now())
           RETURNING id""",
        payload.source_url, payload.agent_id,
    )
    record_id = str(record["id"])
    
    # 3. Enqueue ARQ taak
    await arq_pool.enqueue_job("process_knowledge_upload", record_id)
    
    # 4. Geef direct 202 Accepted terug
    return {"id": record_id, "status": "pending"}
```

HTTP 202 Accepted is de correcte status code voor fire-and-forget: "verzoek ontvangen, verwerking volgt".

### 2.2 Status endpoint toevoegen (als het nog niet bestaat)

```python
@router.get("/knowledge/{record_id}/status")
async def get_knowledge_status(record_id: str, db=Depends(get_db)):
    row = await db.fetchrow(
        "SELECT id, status, error_message, started_at, completed_at FROM knowledge_docs WHERE id=$1::uuid",
        record_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Record niet gevonden")
    return dict(row)
```

Als `GET /api/knowledge/{id}` al bestaat en de status-kolom al retourneert: geen apart status-endpoint nodig.

### 2.3 Frontend: knowledge form

Vervang de blocking await door een optimistic UI-update.

**Patroon:**
```javascript
const handleSubmit = async (formData) => {
  setSubmitting(true);
  
  const response = await api.post('/knowledge', formData);
  // response.status === 202, response.data.status === 'pending'
  
  const { id } = response.data;
  
  // Voeg direct toe aan de lijst met status 'pending'
  setKnowledgeItems(prev => [...prev, { id, status: 'pending', ...formData }]);
  setSubmitting(false);
  
  // Sluit form / reset
  resetForm();
  
  // Geen await op verwerking — gebruiker kan weg navigeren
};
```

Statusweergave in de lijst (hergebruik bestaande badge-component):
- `pending` → grijze badge "Wacht op verwerking..."
- `processing` → blauwe badge "Wordt verwerkt..."
- `completed` → groene badge "Actief"
- `failed` → rode badge "Mislukt" + error-tekst zichtbaar via tooltip of uitklapveld

**Fase 2 gereed als:** Knowledge form geeft direct feedback terug, item verschijnt in lijst als 'pending', ARQ worker verwerkt en status wordt `completed` of `failed`.

---

## Fase 3 — Client datasource crawl omgebouwd

Pas hetzelfde patroon toe als Fase 2, maar nu voor de client datasource endpoints.

**Pre-flight voor deze fase:**
```bash
# (terminal) Vind de relevante router
grep -rn "datasource\|crawl" app/routers/ app/routes/ --include="*.py" -n | head -20
```

Identificeer:
1. Het POST-endpoint dat een crawl start
2. De service-functie die de sync-crawl doet
3. De frontend component die het form rendert

Pas de drie lagen aan (endpoint → ARQ enqueue, service → standalone functie die vanuit worker aangeroepen kan worden, frontend → 202-patroon).

**Fase 3 gereed als:** Datasource form geeft direct 202 terug, crawl loopt in worker, status update zichtbaar.

---

## Fase 4 — Agent training omgebouwd

Pas hetzelfde patroon toe voor de agent training workflow (URL-based training).

**Pre-flight voor deze fase:**
```bash
# (terminal) Vind training-gerelateerde routes
grep -rn "train\|training\|embed" app/routers/ app/routes/ --include="*.py" -l
grep -rn "train\|training\|embed" app/routers/ app/routes/ --include="*.py" -n | head -30
```

**Let op:** De bestaande CEO Approval Gate voor training moet intact blijven. Het patroon is:
```
CEO keurt training goed → POST /api/agents/{id}/train
    → vroeger: sync embed
    → nu: pending record → ARQ process_agent_training
```

De approval-stap zelf verandert niet. Alleen wat er ná de approval gebeurt.

**Fase 4 gereed als:** Agent training via de UI start direct, verloopt via ARQ, status is zichtbaar op de agent-kaart of training-tab.

---

## Fase 5 — SEO job omgebouwd

Pas hetzelfde patroon toe voor SEO keyword jobs. Dit is de meest kritische: GSC-fetches kunnen lang duren en zijn afhankelijk van externe API's.

**Pre-flight voor deze fase:**
```bash
# (terminal) Vind de SEO router en service
grep -rn "seo\|keyword\|gsc\|search_console" app/routers/ app/routes/ --include="*.py" -l
grep -rn "seo\|keyword\|gsc\|search_console" app/routers/ app/routes/ --include="*.py" -n | head -30
```

**Bijzonderheid SEO:** De SEO job heeft al een `seo_jobs`-tabel met status-tracking (verifieer in pre-flight). Als die tabel al `status` heeft, hoeft er geen schema-wijziging te komen — alleen de sync-verwerking vervangen door ARQ enqueue.

**Verwacht patroon:**
```python
@router.post("/seo/jobs", status_code=202)
async def create_seo_job(payload: SEOJobCreate, db=Depends(get_db), arq_pool=Depends(get_arq_pool)):
    job = await db.fetchrow(
        "INSERT INTO seo_jobs (client_id, keywords, status) VALUES ($1, $2, 'pending') RETURNING id",
        payload.client_id, payload.keywords,
    )
    await arq_pool.enqueue_job("process_seo_job", str(job["id"]))
    return {"job_id": str(job["id"]), "status": "pending"}
```

**Fase 5 gereed als:** SEO form geeft direct 202 terug, job loopt in worker, bestaande polling in `SEOTool.jsx` toont de bijgewerkte status.

---

## Fase 6 — Smoke test alle vier flows

**Alleen uitvoeren als Fasen 2, 3, 4 en 5 allemaal klaar zijn.**

**Worker-crash recovery (Test C) en stuck-recovery:** standaard wacht de app `FIRE_AND_FORGET_STUCK_MINUTES` (**120** minuten). Voor Test C: zet tijdelijk **`FIRE_AND_FORGET_STUCK_MINUTES=1`** in de **systemd override** van de service(s) waar de backend en/of worker draait (waar `recover_stuck_fire_and_forget_work` bij startup loopt). Na de crash-test **`daemon-reload` + herstart** en die override **weer verwijderen** — nooit 1 minuut in productie laten staan.

Voer voor elke flow de volgende test uit en rapporteer het resultaat.

**Auth:** alle genoemde `curl`-calls naar de API (behalve publieke routes) vereisen een geldige Supabase JWT:

`Authorization: Bearer <ACCESS_TOKEN>` (zelfde token als de UI).

**Script:** repo-script met Test A + B (knowledge) en optioneel datasources/agent:

`./scripts/smoke_fire_and_forget.sh` — zie kopcomment voor `ACCESS_TOKEN`, `CLIENT_SLUG`, `AGENT_ID`, `RUN_CRASH_TEST`.

### Test A — Pending → Completed flow

```bash
# Optioneel: worker live volgen
journalctl -u wonderz-worker -f &

# Knowledge (URL) — echte route + velden:
curl -sS -o resp.json -w "%{http_code}" -X POST http://localhost:8090/api/knowledge/upload/url \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","title":"Smoke","doc_type":"sop","domain":"core","function_tag":"general"}'
# Verwacht: HTTP 202; JSON: document_id, status "pending", chunks_stored 0

DOCUMENT_ID="$(python3 -c "import json; print(json.load(open('resp.json'))['document_id'])")"

# Poll embedding lifecycle (niet het document workflow-"status"-veld):
for i in {1..20}; do
  curl -s "http://localhost:8090/api/knowledge/$DOCUMENT_ID" -H "Authorization: Bearer $ACCESS_TOKEN" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('embedding_status'))"
  sleep 3
done
# Verwacht: pending → processing → complete (of failed bij fout)
```

Zelfde patroon voor **datasources** (`POST /api/clients/{slug}/datasources` → 202, poll `GET .../datasources/{id}/status`), **SEO** (`POST /api/seo/upload` multipart → 202, poll `GET /api/seo/status/{job_id}`), **training** (`POST /api/agents/{id}/train` → 202; poll via agent-detail / knowledge sources — super_admin vereist).

### Test B — Browser-weg test

**curl-variant (zelfde verwachting als UI):**

```bash
curl ... POST /api/knowledge/upload/url ... -o resp.json   # 202 + document_id
sleep 30   # geen requests in tussen
# daarna pas pollen op GET /api/knowledge/$DOCUMENT_ID → embedding_status niet eeuwig pending
```

Of via UI: form indienen, tab sluiten, na ~30s overzicht openen — item moet verwerkt zijn of nog lopen (`processing`), niet “verdwenen”.

### Test C — Worker-crash recovery

Zet **vóór** de test tijdelijk `FIRE_AND_FORGET_STUCK_MINUTES=1` in de systemd override van **wonderz-worker** en bij voorkeur ook **wonderz-backend** (recovery draait bij beide startups). Zie waarschuwing bovenaan Fase 6.

```bash
# 1. Dien een knowledge-URL-upload in; wacht tot embedding_status = processing
# 2. Stop de worker abrupt
sudo systemctl stop wonderz-worker

# 3. Wacht (langer dan STUCK-minuten, bv. 65s bij minuten=1)
sleep 65

# 4. Herstart worker (recovery draait bij startup)
sudo systemctl start wonderz-worker

# 5. Logs
journalctl -u wonderz-worker -n 30

# 6. Poll record (met Bearer token)
curl -s "http://localhost:8090/api/knowledge/$DOCUMENT_ID" -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
# Verwacht na recovery: embedding_status = 'failed' (stuck processing → failed), niet eeuwig 'processing'
```

**Na de test:** override-regel verwijderen, `daemon-reload`, services opnieuw starten.

**Fase 6 gereed als:** Alle drie tests slagen voor alle vier de flows.

---

## Wat je NIET doet

- **Geen `asyncio.create_task()` of `threading.Thread()`** als vervanger. Alles via ARQ.
- **Geen nieuwe BackgroundTasks** introduceren — we migreren juist weg van dit patroon.
- **Geen polling in de backend** — de worker krijgt taken via de ARQ Redis queue, niet door de DB te pollen.
- **Geen wijzigingen aan de NEXUS pipeline** of de jobs-flow — die zijn al gemigreerd in de vorige sessie.
- **Geen aparte status-endpoints** als `GET /api/{domein}/{id}` al de status retourneert — hergebruik bestaande endpoints.
- **Geen frontend-refactor** buiten de directe form-submit en status-badge scope — geen TanStack Query migratie hier, dat is een apart item.
- **Geen `git add -A`** — stage alleen de gewijzigde bestanden:
  ```bash
  git add app/worker.py
  git add app/migrations/XXX_fire_and_forget_status.sql
  git add app/routers/<gewijzigde_routers>.py
  git add web_ui/frontend/src/<gewijzigde_componenten>.jsx
  ```
- **Niet deployen zonder smoke test** — Fase 6 is verplicht.

---

## Acceptatiecriteria

De implementatie is pas klaar als aan **alle** criteria is voldaan:

- [ ] Alle vier forms geven HTTP 202 + `{id, status: "pending"}` terug binnen 500ms
- [ ] ARQ worker logt de start van elke taak: `[ARQ] <task_type> gestart: <id>`
- [ ] Status update zichtbaar in UI zonder pagina-refresh (bestaand polling-mechanisme)
- [ ] Browser kan gesloten worden na form-submit — taak loopt door
- [ ] Bij worker-crash krijgt het record status `failed` met error_message (geen ewig `processing`)
- [ ] Geen synchrone crawl/embed/fetch-aanroepen meer in POST-endpoints
- [ ] HTTP 202 (niet 200) op alle fire-and-forget endpoints
- [ ] Migratie toegevoegd met juist volgnummer en terugrolbaar (DROP COLUMN IF EXISTS)

---

## Commit instructie

Na succesvolle smoke test per fase committen:

```bash
# Na Fase 1+2:
git add app/worker.py app/migrations/XXX_fire_and_forget_status.sql
git add app/routers/knowledge.py web_ui/frontend/src/components/KnowledgeForm.jsx
git commit -m "feat: fire-and-forget knowledge upload via ARQ"

# Na Fase 3:
git add app/routers/datasources.py web_ui/frontend/src/components/DatasourceForm.jsx
git commit -m "feat: fire-and-forget datasource crawl via ARQ"

# Na Fase 4:
git add app/routers/agents.py web_ui/frontend/src/components/AgentTraining.jsx
git commit -m "feat: fire-and-forget agent training via ARQ"

# Na Fase 5:
git add app/routers/seo.py web_ui/frontend/src/pages/SEOTool.jsx
git commit -m "feat: fire-and-forget SEO job via ARQ"
```

Daarna één deploy:

```bash
git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build
```

---

## Referentiedocumenten

- `260320_CURSOR_arq_persistent_jobs.md` — ARQ architectuur en WorkerSettings (basis voor deze implementatie)
- `crew_intelligent_spec_v1_3.docx` — platformarchitectuur, evidence model, agent anatomie
- `crew_intelligent_product_spec_v1_1.docx` — job lifecycle, status machine, agent lifecycle
- `crew_intelligent_status_v2.md` — huidige staat van de implementatie

---

*Principe: de server draait door, ook als jij er niet bij bent. Dit geldt niet alleen voor jobs maar voor alles wat tijd kost.*
