# 260317_Wonderz_Latency-Optimalisatie

Stack: FastAPI / React / PostgreSQL / Anthropic Claude  
Versie: 1.1 | Maart 2026

---

## Doel

Reduceer de ervaren latency in Wonderz-Agentics structureel over vier lagen: Anthropic API-calls, databasetoegang, backend-logica en frontend-perceptie. Alle winstpercentages in dit document zijn hypotheses totdat een baseline is vastgesteld via Week 0 observability.

---

## Wat je NIET doet

- Geen functionele wijzigingen aan business logic, routes of agent-gedrag
- Geen `git add -A` — stage alleen expliciet gewijzigde bestanden
- Geen optimalisaties uitvoeren voordat Week 0 metingen beschikbaar zijn
- Geen deploy terwijl een andere Cursor-job uncommitted wijzigingen heeft op dezelfde bestanden

---

## Week 0 — Observability (verplichte baseline)

Start hier. Geen verdere stappen zonder meetbare baseline.

**Pre-flight checks:**
```sql
-- Huidige traagste queries identificeren
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Implementatie:**

1. Voeg per NEXUS-fase een structured log-entry toe met tijdstempel en correlatie-ID:
```python
import time, uuid
trace_id = str(uuid.uuid4())  # correlatie-ID per job
phase_start = time.perf_counter()
# ... fase-logica ...
logger.info({
    "trace_id": trace_id,
    "phase": "research",
    "duration_ms": (time.perf_counter() - phase_start) * 1000
})
```

2. Koppel elke Anthropic-call aan het Claude `request-id` (aanwezig in response headers) en log dit samen met het `job_id`

3. Activeer PostgreSQL slow query log tijdelijk (diagnoseperiode):
```
log_min_duration_statement = 200
```
> ⚠️ `logging_collector` kan onder hoge load blocking worden. Noteer herstelmoment en zet terug naar `-1` na diagnose.

4. Draai `EXPLAIN ANALYZE` op de drie traagste queries voor index-analyse

**Wat te meten:**
- End-to-end job latency: p50, p95, p99 per job-type
- TTFT (Time To First Token) per Anthropic-call in streaming-context
- DB-queries: p95 per query-type
- Frontend: Time To Interactive + tijd tot eerste WebSocket event

**Acceptatiecriteria Week 0:**
- Alle NEXUS-fases loggen duration_ms
- Slow query log actief en top 10 queries geïdentificeerd
- Bottleneck-prioriteiten bijgesteld op basis van gemeten data

---

## Week 1 — Database Optimalisatie

### A. Asyncpg driver migratie

**Pre-flight:**
```bash
grep -r "create_engine\|psycopg2" app/
```

Vervang synchrone psycopg2 door asyncpg via SQLAlchemy 2.0+:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/wonderz",
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
)
```

- Vervang alle `SessionLocal` door `AsyncSession` in `async def` endpoints
- Controleer alle `db.close()` calls op async context-veiligheid
- Pool-instellingen zijn startpunten — kalibreer op basis van gemeten concurrency

> ⚠️ Blocking DB-calls in `async def` blokkeren de event loop. FastAPI draait `def` endpoints automatisch in een threadpool; blocking I/O is daar minder problematisch maar `async def` met blocking calls is altijd fout.

**Acceptatiecriteria:**
- Backend start zonder errors na `sudo systemctl restart wonderz-backend`
- Alle bestaande endpoints geven dezelfde responses
- Geen synchrone DB-call meer in een `async def` context

### B. Partial index op jobs(status)

Een gewone index op `jobs(status)` helpt nauwelijks als 90% van de rijen `completed` of `cancelled` is. Gebruik een partial index:

```sql
-- Partial index: alleen actieve statussen
CREATE INDEX CONCURRENTLY idx_jobs_active
    ON jobs(status)
    WHERE status NOT IN ('completed', 'cancelled', 'failed');

-- Aanvullende indexes
CREATE INDEX CONCURRENTLY idx_agent_runs_job_id ON agent_runs(job_id);
CREATE INDEX CONCURRENTLY idx_agent_runs_created ON agent_runs(created_at DESC);
```

> ⚠️ `CREATE INDEX CONCURRENTLY` kan NIET worden uitgevoerd binnen een transaction block. Draai als losse statement buiten BEGIN/COMMIT. Bij een fout blijft een INVALID index achter — herstelstap: `DROP INDEX idx_naam;` gevolgd door opnieuw aanmaken, of `REINDEX INDEX CONCURRENTLY idx_naam`.

### C. Token budget enforcement

- Controleer en stel `max_tokens` bij per NEXUS-fase op basis van Week 0 gemeten output-lengtes
- Injecteer alleen relevante context per stap, niet de volledige systeemprompt

---

## Week 2 — LLM Optimalisatie

### A. Model routing op taakniveau

Gebruik snapshot-IDs voor deterministische resultaten in productie:

| Taaktype | Model (snapshot ID) | Reden |
|---|---|---|
| Data formatteren / extraheren / vertalen | `claude-haiku-4-5-20251001` | Laagste latency, goedkoopst |
| Analyseren / samenvatten / redeneren | `claude-sonnet-4-6` | Balans snelheid + kwaliteit |
| CEO-orchestratie / complexe strategie | `claude-sonnet-4-6` | Sonnet 4.6 volstaat voor orkestratie |
| Diepe content / creatief schrijven | `claude-opus-4-6` | Alleen als kwaliteit het vereist |

Implementeer een `task_complexity` veld in het SkillRegistry of HandoffContext zodat de CEO automatisch het juiste model selecteert.

### B. Anthropic Prompt Caching

Hergebruik de KV-cache voor vaste promptprefixen: CEO-systeemprompt, vaste tool-schema's en vaste Client Knowledge Hub contextblokken.

```python
system_prompt = [
    {
        "type": "text",
        "text": CEO_SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"}
    },
    {
        "type": "text",
        "text": client_knowledge_context,
        "cache_control": {"type": "ephemeral"}
    }
]
```

- Variabele blokken (job-specifieke input) krijgen **geen** `cache_control`
- Log `cache_creation_input_tokens` en `cache_read_input_tokens` uit de response voor monitoring
- Prompt caching is de eerste caching-laag; Redis semantic caching is de tweede laag voor semantisch gelijke volledige requests

---

## Week 3 — Parallelle Uitvoering en Streaming

### A. Parallelle agent-uitvoering

Alleen onafhankelijke stappen kunnen parallel. Breng eerst per job-type in kaart welke stappen afhankelijk zijn van elkaars output.

```python
import asyncio

semaphore = asyncio.Semaphore(5)  # max 5 gelijktijdige Anthropic-calls

async def run_with_limit(agent_fn, context):
    async with semaphore:
        return await agent_fn(context)

results = await asyncio.gather(
    run_with_limit(run_research_agent, context),
    run_with_limit(run_competitor_agent, context),
    run_with_limit(run_audience_agent, context),
)
```

Implementeer exponential backoff retry per agent-call voor 529/429 errors.

> ⚠️ Claude kan een `529 overloaded_error` retourneren. Bij streaming kan een error ook optreden nadat al een 200-response gestart is: de UI moet partial output plus een errorstate kunnen tonen.

### B. Streaming end-to-end

```python
async with client.messages.stream(
    model=model_id,
    messages=messages,
    max_tokens=max_tokens,
) as stream:
    async for text in stream.text_stream:
        await websocket.send_text(text)
```

- Vang stream-level errors expliciet op
- Stuur een duidelijk error-event naar de frontend bij streaming-fouten
- Koppel fase-status events aan de bestaande WebSocket infrastructuur:
  - Fase 1: `"Briefing aan het verwerken..."`
  - Fase 3: `"Research agent actief..."`
  - Fase 6: `"Kwaliteitscontrole..."`

---

## Week 4 — Frontend Optimalisatie

### A. TanStack Query caching

> ⚠️ In TanStack Query v5 is `cacheTime` hernoemd naar `gcTime`. Controleer versie voor implementatie. Defaults: `staleTime = 0`, `gcTime = 5 minuten`.

```javascript
// TanStack Query v5
const { data } = useQuery({
    queryKey: ['jobs'],
    queryFn: fetchJobs,
    staleTime: 30_000,   // 30 seconden
    gcTime: 300_000,     // 5 minuten (voorheen cacheTime)
})
```

Gebruik optimistic updates bij statuswijzigingen.

### B. BackgroundTasks audit

Verplaats logging, notificaties en audit-schrijf-operaties naar `FastAPI BackgroundTasks`.

> ⚠️ Synchrone BackgroundTasks draaien in FastAPI's threadpool (standaard 40 tokens). Zware of langlopende taken (batch-verwerking, externe notificaties) naar een aparte worker queue: Celery of ARQ.

---

## Week 5+ — Semantic Caching

Implementeer Redis semantic caching als aanvulling op Anthropic Prompt Caching. Definieer eerst een concrete herhalingsdrempel op basis van Week 0-4 data (welk percentage van jobs is semantisch gelijk?). Dit is een hypothese van 60-90% winst op herhalingen totdat gemeten.

---

## Deployment

```bash
cd ~/wonderz-agentics && git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build
```

Stage altijd expliciet — nooit `git add -A`.

---

## Fase-rapportage

Rapporteer na elke week:
- Gemeten p95 voor en na
- Welke bestanden gewijzigd
- Eventuele blockers (documenteer in dit bestand, ga door met volgende fase)
