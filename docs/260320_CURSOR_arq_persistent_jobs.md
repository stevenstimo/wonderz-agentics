# 260320 — Crew Intelligent: ARQ Persistent Job Processing

**Versie:** 1.0  
**Datum:** 20 maart 2026  
**Status:** Klaar voor uitvoering  
**Doel:** Vervang FastAPI BackgroundTasks door ARQ zodat jobs server-side doordraaien, ook als de browser of laptop gesloten is.

---

## Context

De huidige architectuur gebruikt `FastAPI BackgroundTasks` voor job-uitvoering. Dit heeft drie concrete problemen:

1. **Niet persistent** — Als de backend herstart terwijl een job loopt, stopt de taak halverwege. De job blijft op `RUNNING` hangen.
2. **Geen recovery** — Er is geen mechanisme dat bij herstart kijkt welke jobs op `RUNNING` staan en die hervat of naar `FAILED` zet.
3. **In-process** — De taak leeft in de threadpool van het webproces. Backend-crash = job-crash.

**Gekozen oplossing: ARQ**

ARQ is asyncio-native, draait als apart proces, gebruikt Redis als queue en past naadloos op de bestaande FastAPI + asyncpg stack. Celery is bewust afgewezen: zwaarder, synchroon van karakter, overkill voor deze stack.

Na deze implementatie:
- Jobs draaien in een apart ARQ worker-proces
- De ARQ worker heeft een eigen systemd service (`crew-worker.service`) met `Restart=always`
- Een startup-hook scant voor stuck `RUNNING` jobs en zet die op `FAILED` met reden
- De browser/laptop kan gesloten worden zonder dat een lopende job stopt

---

## Pre-flight checklist

Voer deze checks uit vóór je begint. Bij een falende check: stop en meld het resultaat.

```bash
# 1. Redis beschikbaar?
redis-cli ping
# verwacht: PONG

# 2. ARQ geïnstalleerd?
python3 -c "import arq; print(arq.__version__)"
# als niet: pip install arq --break-system-packages

# 3. Jobs tabel aanwezig?
python3 -c "
import asyncio, asyncpg, os
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    r = await conn.fetchval('SELECT COUNT(*) FROM jobs')
    print(f'jobs rows: {r}')
    await conn.close()
asyncio.run(check())
"

# 4. Huidige BackgroundTasks locatie vinden
grep -rn "BackgroundTasks\|add_task\|background_tasks" app/ --include="*.py"
# Noteer alle locaties — die moeten worden gemigreerd

# 5. Systemd service naam opzoeken
systemctl list-units | grep crew
```

Rapporteer de output van elke check vóór je naar Fase 1 gaat.

---

## Fasering

Werk fasen strikt in volgorde. Geen twee fasen tegelijk.  
Na elke fase: rapporteer wat gebouwd is en wacht op bevestiging.

| Fase | Beschrijving | Prioriteit |
|------|-------------|------------|
| 1 | Redis + ARQ installatie & configuratie | Blocker |
| 2 | ARQ WorkerSettings + taakdefinities | Blocker |
| 3 | FastAPI integratie: ARQ pool + enqueue | Blocker |
| 4 | Job recovery bij herstart | Hoog |
| 5 | Systemd worker service | Blocker |
| 6 | Smoke test end-to-end | Hoog |

---

## Fase 1 — Redis + ARQ setup

### 1.1 Redis

Controleer of Redis al draait:

```bash
systemctl status redis-server
```

Als Redis niet draait:

```bash
sudo apt install redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping  # moet PONG teruggeven
```

### 1.2 ARQ installeren

```bash
pip install arq --break-system-packages
```

Voeg toe aan `requirements.txt`:

```
arq>=0.25.0
```

### 1.3 Redis URL in environment

Voeg toe aan het systemd override bestand (`/etc/systemd/system/<service>.service.d/override.conf`):

```ini
[Service]
Environment="REDIS_URL=redis://localhost:6379"
```

Voeg ook toe aan `.env` (voor lokale ontwikkeling):

```
REDIS_URL=redis://localhost:6379
```

**Fase 1 gereed als:** `redis-cli ping` → PONG, `import arq` werkt zonder errors.

---

## Fase 2 — ARQ WorkerSettings en taakdefinities

### 2.1 Maak `app/worker.py`

Dit bestand definieert de ARQ worker en alle taken die hij uitvoert.

```python
"""
app/worker.py
ARQ worker configuratie voor Crew Intelligent.
Vervangt FastAPI BackgroundTasks voor alle job-uitvoering.
"""
import logging
import os
from arq import cron
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


# ── Taak: volledige job pipeline uitvoeren ──────────────────────────────────

async def run_job_pipeline(ctx: dict, job_id: str) -> dict:
    """
    Voert de volledige job pipeline uit voor een gegeven job_id.
    Vervangt de vorige BackgroundTasks implementatie.
    
    ctx bevat: redis (ARQ pool), db_pool (asyncpg, toegevoegd in startup)
    """
    from app.orchestration.nexus_pipeline import run_nexus_pipeline  # noqa — import hier om circular imports te vermijden
    
    logger.info(f"[ARQ] Job gestart: {job_id}")
    
    try:
        result = await run_nexus_pipeline(job_id=job_id, db_pool=ctx["db_pool"])
        logger.info(f"[ARQ] Job voltooid: {job_id}")
        return {"job_id": job_id, "status": "completed", "result": result}
    except Exception as e:
        logger.exception(f"[ARQ] Job gefaald: {job_id} — {e}")
        # Markeer job als FAILED in DB
        await _mark_job_failed(ctx["db_pool"], job_id, str(e))
        raise


async def _mark_job_failed(db_pool, job_id: str, reason: str) -> None:
    """Zet job status op FAILED met foutmelding."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE jobs
            SET status = 'FAILED',
                updated_at = now(),
                error_message = $1
            WHERE job_id = $2
            """,
            reason,
            job_id,
        )


# ── Startup: recovery van stuck RUNNING jobs ──────────────────────────────

async def startup(ctx: dict) -> None:
    """
    Wordt uitgevoerd bij elke worker-start.
    Scant voor jobs die op RUNNING zijn blijven hangen na een crash
    en zet die op FAILED zodat ze opnieuw ingepland kunnen worden.
    """
    import asyncpg

    db_url = os.environ["DATABASE_URL"]
    ctx["db_pool"] = await asyncpg.create_pool(db_url, min_size=2, max_size=10)

    pool = ctx["db_pool"]
    async with pool.acquire() as conn:
        stuck_jobs = await conn.fetch(
            """
            SELECT job_id, updated_at
            FROM jobs
            WHERE status = 'RUNNING'
              AND updated_at < now() - interval '10 minutes'
            """
        )

        if stuck_jobs:
            logger.warning(
                f"[ARQ] Recovery: {len(stuck_jobs)} stuck RUNNING job(s) gevonden"
            )
            for row in stuck_jobs:
                await conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'FAILED',
                        updated_at = now(),
                        error_message = 'Worker herstart terwijl job liep. Handmatig opnieuw starten.'
                    WHERE job_id = $1
                    """,
                    row["job_id"],
                )
                logger.warning(
                    f"[ARQ] Job {row['job_id']} gezet op FAILED (was stuck sinds {row['updated_at']})"
                )
        else:
            logger.info("[ARQ] Startup recovery: geen stuck jobs gevonden.")


async def shutdown(ctx: dict) -> None:
    """Sluit de DB pool netjes af bij worker shutdown."""
    if "db_pool" in ctx:
        await ctx["db_pool"].close()
        logger.info("[ARQ] DB pool gesloten.")


# ── WorkerSettings ──────────────────────────────────────────────────────────

class WorkerSettings:
    """
    ARQ WorkerSettings. Wordt gebruikt door de `arq` CLI en de systemd service.
    
    Start worker via:
        arq app.worker.WorkerSettings
    """
    functions = [run_job_pipeline]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379")
    )
    max_jobs = 10
    job_timeout = 3600         # 1 uur max per job
    keep_result = 86400        # resultaten 24 uur bewaren in Redis
    retry_jobs = False         # geen automatische retry — CEO beslist opnieuw starten
    health_check_interval = 60
```

**Let op:** De import van `run_nexus_pipeline` staat bewust binnenin de functie. Dit voorkomt circular imports bij het laden van de worker module.

**Fase 2 gereed als:** `python3 -c "from app.worker import WorkerSettings; print('OK')"` werkt zonder errors.

---

## Fase 3 — FastAPI integratie: ARQ pool + enqueue

### 3.1 ARQ pool aanmaken in `app/main.py`

Voeg toe aan de lifespan/startup van de FastAPI app:

```python
# Bovenaan main.py toevoegen
from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
import os

# In de lifespan context manager of @app.on_event("startup"):
@app.on_event("startup")
async def startup_event():
    # Bestaande startup code (DB pool, etc.) blijft staan
    # ...
    
    # ARQ pool aanmaken en opslaan in app.state
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379")
    )
    app.state.arq_pool = await arq_create_pool(redis_settings)


@app.on_event("shutdown")
async def shutdown_event():
    # ARQ pool sluiten
    if hasattr(app.state, "arq_pool"):
        await app.state.arq_pool.close()
```

### 3.2 Dependency: ARQ pool ophalen

Voeg toe aan `app/dependencies.py` (of maak dit bestand aan als het niet bestaat):

```python
from fastapi import Request
from arq import ArqRedis

async def get_arq_pool(request: Request) -> ArqRedis:
    """Dependency om de ARQ pool op te halen vanuit app.state."""
    return request.app.state.arq_pool
```

### 3.3 Verwijder BackgroundTasks, vervang door ARQ enqueue

Zoek alle locaties gevonden in de pre-flight check. Voor **elke** locatie:

**Oud patroon:**
```python
# Ergens in een endpoint
background_tasks.add_task(run_job_pipeline, job_id)
```

**Nieuw patroon:**
```python
from app.dependencies import get_arq_pool
from fastapi import Depends
from arq import ArqRedis

@router.post("/jobs/{job_id}/start")
async def start_job(
    job_id: str,
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    # Zet job op RUNNING in DB
    await update_job_status(job_id, "RUNNING")
    
    # Plaats in ARQ queue — returned onmiddellijk
    await arq_pool.enqueue_job("run_job_pipeline", job_id)
    
    return {"job_id": job_id, "status": "RUNNING", "message": "Job in queue geplaatst"}
```

**Verwijder ook** alle `BackgroundTasks` imports en parameters uit de endpoints die worden gemigreerd.

### 3.4 Verwijder `BackgroundTasks` uit function signatures

Zoek alle endpoints met `background_tasks: BackgroundTasks` als parameter en verwijder die. Vervang door `arq_pool: ArqRedis = Depends(get_arq_pool)`.

**Fase 3 gereed als:** Backend start zonder errors, job-endpoints accepteren requests en geven `RUNNING` terug zonder te wachten op completion.

---

## Fase 4 — Job recovery bij herstart (FastAPI kant)

Naast de ARQ worker startup (die stuck jobs FAILED zet), voeg ook een startup-check toe aan de FastAPI app zelf. Dit zorgt ervoor dat de UI nooit een job toont die "for ever" op RUNNING hangt als de worker er nog niet is.

Voeg toe aan de startup event in `app/main.py`:

```python
async def recover_stuck_jobs(db_pool) -> None:
    """
    Zet jobs die langer dan 10 minuten op RUNNING staan op FAILED.
    Wordt uitgevoerd bij elke backend herstart.
    Dubbele recovery is safe — ARQ worker doet hetzelfde.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    async with db_pool.acquire() as conn:
        stuck = await conn.fetch(
            """
            SELECT job_id FROM jobs
            WHERE status = 'RUNNING'
              AND updated_at < now() - interval '10 minutes'
            """
        )
        for row in stuck:
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'FAILED',
                    updated_at = now(),
                    error_message = 'Backend herstart — job kon niet worden hervat.'
                WHERE job_id = $1
                """,
                row["job_id"],
            )
            logger.warning(f"[Recovery] Job {row['job_id']} → FAILED (stuck bij herstart)")
```

Roep `await recover_stuck_jobs(app.state.db_pool)` aan in de startup event, na het aanmaken van de DB pool.

**Fase 4 gereed als:** Na een handmatige `sudo systemctl restart <backend-service>` verschijnen stuck RUNNING jobs als FAILED in de DB (verifieer met SQL).

---

## Fase 5 — Systemd worker service

Maak een nieuwe systemd service aan voor de ARQ worker. De worker is een volledig los proces van de FastAPI backend.

### 5.1 Service bestand aanmaken

```bash
sudo nano /etc/systemd/system/crew-worker.service
```

Inhoud:

```ini
[Unit]
Description=Crew Intelligent ARQ Worker
After=network.target redis-server.service postgresql.service
Wants=redis-server.service

[Service]
Type=simple
User=exedev
WorkingDirectory=/home/exedev/<repo-pad>
ExecStart=/usr/bin/python3 -m arq app.worker.WorkerSettings
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=crew-worker

[Install]
WantedBy=multi-user.target
```

**Vervang `<repo-pad>`** met het daadwerkelijke pad naar de repo root.

### 5.2 Environment variables voor de worker

Maak een override bestand aan:

```bash
sudo mkdir -p /etc/systemd/system/crew-worker.service.d/
sudo nano /etc/systemd/system/crew-worker.service.d/override.conf
```

Inhoud (kopieer de benodigde vars uit de backend override):

```ini
[Service]
Environment="DATABASE_URL=postgresql://..."
Environment="ANTHROPIC_API_KEY=sk-ant-..."
Environment="REDIS_URL=redis://localhost:6379"
```

### 5.3 Service activeren

```bash
sudo systemctl daemon-reload
sudo systemctl enable crew-worker
sudo systemctl start crew-worker
sudo systemctl status crew-worker
```

Controleer de logs:

```bash
journalctl -u crew-worker -f
```

Je moet zien:
```
[ARQ] Startup recovery: geen stuck jobs gevonden.
Starting worker for functions: run_job_pipeline
```

**Fase 5 gereed als:** `systemctl status crew-worker` → `active (running)`, geen errors in journal.

---

## Fase 6 — Smoke test end-to-end

Voer de volgende verificatiestappen uit en rapporteer de output van elk.

### 6.1 Worker draait en pikt taken op

```bash
# Terminal 1: worker live volgen
journalctl -u crew-worker -f

# Terminal 2: maak een test job aan via de API
curl -X POST http://localhost:8090/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"description": "Schrijf 100 woorden over koffie", "client_id": "test"}'
# Noteer job_id uit response

# Start de job
curl -X POST http://localhost:8090/api/jobs/<job_id>/start
```

Verwacht in de worker logs:
```
[ARQ] Job gestart: <job_id>
```

### 6.2 Laptop-dicht test (simulatie)

```bash
# Start een job
curl -X POST http://localhost:8090/api/jobs/<job_id>/start

# Stop de FRONTEND (niet de backend)
# Wacht 30 seconden

# Controleer status via API
curl http://localhost:8090/api/jobs/<job_id>
# Verwacht: status = RUNNING of COMPLETED, niet leeg of FAILED
```

### 6.3 Backend-crash recovery test

```bash
# Start een job
curl -X POST http://localhost:8090/api/jobs/<job_id>/start

# Forceer een backend restart
sudo systemctl restart <backend-service>

# Controleer: backend en worker zijn beide weer up
systemctl status <backend-service> crew-worker

# Controleer job status na 2 minuten
curl http://localhost:8090/api/jobs/<job_id>
# Verwacht: FAILED met message 'Backend herstart' OF COMPLETED als worker het kon afmaken
```

### 6.4 Stuck job SQL verificatie

```sql
-- Voer uit na de crash-test
SELECT job_id, status, error_message, updated_at
FROM jobs
WHERE status IN ('RUNNING', 'FAILED')
ORDER BY updated_at DESC
LIMIT 10;
```

**Fase 6 gereed als:** Alle drie scenario's gedragen zich correct. Job draait door zonder open browser, worker pikt taken op, stuck jobs worden FAILED gezet na herstart.

---

## Wat je NIET doet

- **Geen Celery** — bewuste keuze. ARQ is de enige queue-implementatie.
- **Geen database-polling in de worker** — de worker krijgt jobs via de ARQ Redis queue, niet door de DB te pollen.
- **Geen in-process threading** — geen `asyncio.create_task()` of `threading.Thread()` als vervanging voor BackgroundTasks. Alles via ARQ.
- **Geen wijzigingen aan de frontend** — de UI polt al op job status via de API. Dat blijft werken.
- **Geen `git add -A`** — stage alleen de bestanden die je hebt aangemaakt of gewijzigd:
  ```bash
  git add app/worker.py app/main.py app/dependencies.py requirements.txt
  git add app/routers/<gewijzigde_router>.py
  ```
- **Niet deployen zonder smoke test** — Fase 6 is verplicht vóór de commit.

---

## Acceptatiecriteria

De implementatie is pas klaar als aan **alle** criteria is voldaan:

- [ ] `redis-cli ping` → PONG op de server
- [ ] `systemctl status crew-worker` → `active (running)`
- [ ] Nieuwe job start zonder dat de FastAPI endpoint blokkeert
- [ ] Job status is zichtbaar in DB als RUNNING terwijl de worker hem uitvoert
- [ ] Na `sudo systemctl restart crew-worker` pikt de worker nieuwe jobs op
- [ ] Stuck RUNNING jobs worden FAILED gezet na herstart (recovery werkt)
- [ ] Job draait door als browser gesloten wordt tijdens uitvoering
- [ ] Geen `BackgroundTasks` imports meer aanwezig in gemigreerde endpoints
- [ ] Worker logs zijn leesbaar via `journalctl -u crew-worker`

---

## Commit instructie

Na succesvolle smoke test:

```bash
git add app/worker.py
git add app/main.py
git add app/dependencies.py
git add requirements.txt
git add app/routers/<gewijzigde_bestanden>.py
git commit -m "feat: replace BackgroundTasks with ARQ persistent job queue"
```

Daarna:

```bash
sudo systemctl daemon-reload
sudo systemctl restart <backend-service>
sudo systemctl restart crew-worker
```

---

## Referentiedocumenten

- `crew_intelligent_spec_v1_3.docx` — platformarchitectuur, event model, job statussen
- `crew_intelligent_product_spec_v1_1.docx` — job lifecycle, status machine
- `crew_intelligent_status_v2.md` — huidige staat van de implementatie
- `260317_crew_intelligent_agent_framework.md` — agent anatomie en pipeline

---

*Doel van deze implementatie: de crew draait server-side door, ook als jij er niet bij bent. Dat is het fundament waarop alles else is gebouwd.*
