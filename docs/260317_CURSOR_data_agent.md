# 260317 — Data Agent & Intentiedetectie Laag
**Doel:** Implementeer `agent:data-analyst` en de intentiedetectie routing in `IntakeEngine`, zodat data-opvraag jobs een eigen pipeline krijgen los van de content creation pipeline.

---

## Architecturele context

De CEO-orchestrator behandelt nu alle jobs als content creation opdrachten: altijd copy_agent → reviewer_agent → CEO check. Dit is onjuist voor jobs waarbij de gebruiker data wil ophalen ("toon mij de top pagina's", "geef klikdata", "overzicht van impressions").

Dit document implementeert twee samenhangende componenten:

1. **`agent:data-analyst`** — een nieuwe Worker-agent die data ophaalt en presenteert, zonder content te schrijven.
2. **`IntakeEngine._detect_task_type()`** — een routing laag die het jobtype detecteert, op volledigheid controleert, en de juiste pipeline activeert.

De twee componenten zijn onlosmakelijk verbonden. Implementeer ze in één sessie, in de volgorde van de fases hieronder.

---

## Wat dit NIET is

- Geen quick fix op de bestaande copy_agent of reviewer_agent.
- Geen aanpassing van de content creation pipeline.
- Geen nieuw status-type buiten de bestaande job status machine — `INTAKE_CLARIFICATION`, `PLAN_PROPOSED`, `RUNNING`, `JOB_READY`, `COMPLETED` blijven ongewijzigd. Wél een nieuw intern routing-label `DIRECT_RESPONSE` dat intern door de CEO wordt gebruikt maar geen aparte DB-status is.
- Geen UI-wijzigingen aan ReviewDiff of LiveTracker, tenzij expliciet vermeld.

---

## Pre-flight checks

Voer deze controles uit vóór je begint. Stop bij elke fout en meld wat er mis is.

```sql
-- (SQL) Lokale postgres
-- 1. Bestaat de hired_agents tabel?
SELECT agent_id, role, is_active
FROM hired_agents
ORDER BY created_at DESC
LIMIT 10;

-- 2. Bestaat de jobs tabel met de juiste status-kolom?
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'jobs'
ORDER BY ordinal_position;

-- 3. Welke agents zijn al aangemaakt?
SELECT agent_id, role, tool_whitelist
FROM hired_agents
WHERE is_active = true;

-- 4. Bestaat de job_steps tabel?
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'job_steps'
ORDER BY ordinal_position;
```

```bash
# (terminal)
# 5. Bestaat de IntakeEngine al?
find app/ -name "intake_engine.py" 2>/dev/null || echo "ONTBREEKT"

# 6. Bestaat de copy_agent?
find app/ -name "copy_agent.py" 2>/dev/null || echo "ONTBREEKT"

# 7. Welke orchestrator bestanden bestaan er al?
ls app/orchestrator/ 2>/dev/null || ls app/agents/ 2>/dev/null || echo "Controleer mapstructuur"

# 8. Welke routes zijn geregistreerd?
grep -n "router\|include_router" app/main.py
```

Rapporteer de output van alle acht checks vóór je verder gaat.

---

## Fase 1 — DB: data_analyst agent aanmaken

**Wat:** Voeg `agent:data-analyst` toe aan de `hired_agents` tabel. Dit is het fundament: alle routing in de volgende fasen verwijst naar dit agent_id.

```sql
-- (SQL) Lokale postgres
INSERT INTO hired_agents (
  agent_id,
  agent_name,
  role,
  goal,
  system_prompt,
  tool_whitelist,
  knowledge_sources,
  is_active,
  is_suspended
) VALUES (
  'agent:data-analyst',
  'Data Analyst',
  'data-analyst',
  'Haal data op uit beschikbare databronnen en presenteer deze als gestructureerde, leesbare output. Schrijf geen content. Maak geen aanbevelingen tenzij expliciet gevraagd.',
  'Je bent een Data Analyst agent binnen een multi-agent marketing platform.

Je taak is uitsluitend het ophalen en presenteren van data. Je schrijft geen teksten, geen adviezen en geen aanbevelingen tenzij expliciet gevraagd.

Werkwijze:
1. Ontvang een data-query met parameters: datasource, metric, period, top_k, client_slug.
2. Haal de data op via de tool die bij de datasource hoort.
3. Presenteer de data als een gestructureerde tabel of genummerde lijst.
4. Voeg altijd toe: welke periode, welke bron, en het aantal resultaten.
5. Als data ontbreekt of de bron niet beschikbaar is: meld dit expliciet. Vul nooit in wat er niet is.

Output contract (verplicht):
- Gevonden: wat is er opgehaald, van welke bron, over welke periode
- Resultaat: de data als tabel of lijst
- Volledigheid: zijn er gaps of lege waarden? Vermeld ze expliciet
- Volgende actie: wat kan de gebruiker doen met deze data (optioneel, max 1 zin)

Je antwoord is altijd in het Nederlands tenzij de query in een andere taal is gesteld.
Nooit meer dan gevraagd. Geen padders, geen intro-teksten.',
  ARRAY['read_gsc', 'read_analytics', 'read_client_knowledge', 'format_table'],
  '[]'::jsonb,
  true,
  false
);
```

**Verificatie na uitvoering:**
```sql
SELECT agent_id, role, tool_whitelist, is_active
FROM hired_agents
WHERE agent_id = 'agent:data-analyst';
```

Verwacht resultaat: 1 rij, `is_active = true`, tool_whitelist bevat 4 tools.

**Stop en bevestig** dat deze verificatie slaagt voor je naar fase 2 gaat.

---

## Fase 2 — Backend: `_detect_task_type()` in IntakeEngine

**Wat:** Voeg een privé-methode toe aan de bestaande `IntakeEngine` class die het jobtype detecteert en een volledigheidscheck uitvoert specifiek voor dat type.

**Bestand:** `app/orchestrator/intake_engine.py` (of het equivalent in jouw mapstructuur — verifieer eerst via pre-flight check 5)

### 2.1 Jobtype-taxonomie

De methode herkent drie types. Implementeer ze in de volgorde van prioriteit: controleer `data_query` eerst, dan `seo_task`, dan `content_creation` als fallback.

| Type | Signaalwoorden (case-insensitive, Nederlands + Engels) |
|---|---|
| `data_query` | toon, geef, lijst, overzicht, top, hoeveel, klikdata, impressions, clicks, ctr, positie, ranking, verkeer, traffic, bezoekers, rapport, rapportage, stats, statistieken, show me, give me, list, overview |
| `seo_task` | zoekwoord, keyword, meta, title tag, h1, h2, slug, canoniek, seo, serp, backlink, ankertekst |
| `content_creation` | (fallback — alles wat niet data_query of seo_task is) |

### 2.2 Completeness check per jobtype

De methode controleert ook welke parameters ontbreken. Elke parameters heeft een default-waarde of is kritiek (= moet gevraagd worden).

**Voor `data_query`:**

| Parameter | Kritiek? | Default als niet kritiek |
|---|---|---|
| `client_slug` | Ja, als er meerdere clients zijn | Geen default — altijd vragen |
| `site_url` | Ja, als GSC meerdere properties heeft | Geen default — altijd vragen |
| `period_days` | Nee | 28 |
| `metric` | Nee | `['clicks', 'impressions']` |
| `top_k` | Nee | 10 |
| `datasource` | Nee | `'gsc'` als GSC beschikbaar, anders `'client_knowledge'` |

**Voor `seo_task`:** (nog geen actieve pipeline — retourneer `task_type: 'seo_task'`, behandel als `content_creation` tot seo-pipeline bestaat)

**Voor `content_creation`:** bestaand pad, geen wijziging.

### 2.3 Code

Voeg de volgende methode toe aan de `IntakeEngine` class:

```python
def _detect_task_type(self, raw_text: str, job_context: dict) -> dict:
    """
    Detecteert het jobtype op basis van signaalwoorden in de opdracht.
    Voert een completeness check uit specifiek voor het gedetecteerde type.

    Returns:
        {
            "task_type": "data_query" | "seo_task" | "content_creation",
            "is_complete": bool,
            "missing_params": list[str],      # kritieke ontbrekende params
            "defaults_applied": dict,          # params ingevuld met defaults
            "query_params": dict               # volledig param-object voor data_agent
        }
    """
    text_lower = raw_text.lower()

    # --- Stap 1: Detecteer jobtype ---
    DATA_QUERY_SIGNALS = [
        "toon", "geef", "lijst", "overzicht", "top ", "hoeveel",
        "klikdata", "impressions", "clicks", "ctr", "positie",
        "ranking", "verkeer", "traffic", "bezoekers", "rapport",
        "rapportage", "stats", "statistieken",
        "show me", "give me", "list", "overview"
    ]
    SEO_TASK_SIGNALS = [
        "zoekwoord", "keyword", "meta", "title tag", "h1", "h2",
        "slug", "canoniek", "serp", "backlink", "ankertekst"
    ]

    if any(signal in text_lower for signal in DATA_QUERY_SIGNALS):
        task_type = "data_query"
    elif any(signal in text_lower for signal in SEO_TASK_SIGNALS):
        task_type = "seo_task"
    else:
        task_type = "content_creation"

    # --- Stap 2: Completeness check (alleen voor data_query) ---
    if task_type != "data_query":
        return {
            "task_type": task_type,
            "is_complete": True,
            "missing_params": [],
            "defaults_applied": {},
            "query_params": {}
        }

    missing_params = []
    defaults_applied = {}
    query_params = {}

    # Client slug — kritiek als meerdere clients beschikbaar
    client_slug = job_context.get("client_slug")
    available_clients = job_context.get("available_clients", [])
    if not client_slug:
        if len(available_clients) > 1:
            missing_params.append("client_slug")
        elif len(available_clients) == 1:
            client_slug = available_clients[0]
            defaults_applied["client_slug"] = client_slug
        # als geen clients bekend: geen kritieke fout, data_agent meldt dit zelf
    query_params["client_slug"] = client_slug

    # Site URL — kritiek als GSC meerdere properties heeft
    site_url = job_context.get("site_url") or job_context.get("gsc_site_url")
    gsc_properties = job_context.get("gsc_properties", [])
    if not site_url:
        if len(gsc_properties) > 1:
            missing_params.append("site_url")
        elif len(gsc_properties) == 1:
            site_url = gsc_properties[0]
            defaults_applied["site_url"] = site_url
    query_params["site_url"] = site_url

    # Period — niet kritiek, default 28 dagen
    period_days = job_context.get("period_days")
    if not period_days:
        period_days = 28
        defaults_applied["period_days"] = period_days
    query_params["period_days"] = period_days

    # Metric — niet kritiek, default clicks + impressions
    metric = job_context.get("metric")
    if not metric:
        metric = ["clicks", "impressions"]
        defaults_applied["metric"] = metric
    query_params["metric"] = metric

    # Top K — niet kritiek, default 10
    top_k = job_context.get("top_k") or _extract_top_k(raw_text)
    if not top_k:
        top_k = 10
        defaults_applied["top_k"] = top_k
    query_params["top_k"] = top_k

    # Datasource — niet kritiek, default GSC
    datasource = job_context.get("datasource", "gsc")
    query_params["datasource"] = datasource

    return {
        "task_type": "data_query",
        "is_complete": len(missing_params) == 0,
        "missing_params": missing_params,
        "defaults_applied": defaults_applied,
        "query_params": query_params
    }


def _extract_top_k(text: str) -> int | None:
    """Extraheert 'top X' getal uit vrije tekst. Bijv. 'top 5 paginas' -> 5."""
    import re
    match = re.search(r'\btop\s+(\d+)\b', text.lower())
    if match:
        return int(match.group(1))
    return None
```

### 2.4 Integreer in `analyze_job_post`

Pas de bestaande `analyze_job_post` methode aan zodat deze `_detect_task_type()` aanroept en het resultaat meestuurt:

```python
def analyze_job_post(self, raw_text: str, job_context: dict) -> dict:
    # --- Bestaande logica intact laten ---
    # Voeg toe VÓÓR de LLM-call voor clarification questions:

    type_detection = self._detect_task_type(raw_text, job_context)

    # Sla het gedetecteerde type op in job_context voor downstream gebruik
    job_context["detected_task_type"] = type_detection["task_type"]
    job_context["query_params"] = type_detection.get("query_params", {})
    job_context["defaults_applied"] = type_detection.get("defaults_applied", {})

    # Data query met ontbrekende kritieke params -> gerichte vraag
    if type_detection["task_type"] == "data_query" and not type_detection["is_complete"]:
        clarification_questions = _build_data_clarification_questions(
            type_detection["missing_params"],
            job_context
        )
        return {
            "is_complete": False,
            "task_type": "data_query",
            "clarification_questions": clarification_questions,
            "query_params": type_detection["query_params"],
            "defaults_applied": type_detection["defaults_applied"]
        }

    # Data query volledig -> direct doorsturen, geen LLM intake nodig
    if type_detection["task_type"] == "data_query" and type_detection["is_complete"]:
        return {
            "is_complete": True,
            "task_type": "data_query",
            "clarification_questions": [],
            "query_params": type_detection["query_params"],
            "defaults_applied": type_detection["defaults_applied"]
        }

    # Alle andere types -> bestaande LLM-gebaseerde intake (ongewijzigd)
    # ... bestaande code ...
```

Voeg ook deze hulpfunctie toe (buiten de class):

```python
def _build_data_clarification_questions(missing_params: list[str], job_context: dict) -> list[str]:
    """
    Bouwt gerichte keuzevragen voor ontbrekende kritieke parameters.
    Altijd max 1 vraag per parameter. Geen open vragen — altijd met opties.
    """
    questions = []
    available_clients = job_context.get("available_clients", [])
    gsc_properties = job_context.get("gsc_properties", [])

    if "client_slug" in missing_params and available_clients:
        options = " / ".join(available_clients)
        questions.append(f"Voor welke klant wil je de data? ({options})")

    if "site_url" in missing_params and gsc_properties:
        options = " / ".join(gsc_properties)
        questions.append(f"Voor welke website wil je de data? ({options})")

    return questions
```

**Verificatie na implementatie:**
```python
# (cursor) Voeg tijdelijk toe aan een testbestand of run direct in REPL:
engine = IntakeEngine()

# Test 1: volledig data_query
result = engine._detect_task_type(
    "toon mij de top 10 paginas",
    {"client_slug": "asured", "site_url": "https://asured.nl", "gsc_properties": ["https://asured.nl"]}
)
assert result["task_type"] == "data_query"
assert result["is_complete"] == True
assert result["query_params"]["top_k"] == 10
print("Test 1 OK:", result)

# Test 2: data_query met ontbrekende client
result = engine._detect_task_type(
    "geef mij een overzicht van de klikdata",
    {"available_clients": ["asured", "merk-b"], "gsc_properties": ["https://asured.nl"]}
)
assert result["task_type"] == "data_query"
assert result["is_complete"] == False
assert "client_slug" in result["missing_params"]
print("Test 2 OK:", result)

# Test 3: content_creation (geen signaalwoorden)
result = engine._detect_task_type(
    "schrijf een blogpost over onze nieuwe collectie",
    {}
)
assert result["task_type"] == "content_creation"
print("Test 3 OK:", result)
```

**Stop en bevestig** dat alle drie tests slagen voor je naar fase 3 gaat.

---

## Fase 3 — Backend: `data_agent.py`

**Wat:** Implementeer de `DataAgent` class die data ophaalt en presenteert als gestructureerde output. Dit is de Worker die `agent:data-analyst` uitvoert.

**Bestand:** `app/agents/data_agent.py` (nieuw bestand)

```python
# app/agents/data_agent.py
"""
DataAgent — Worker voor data-opvraag jobs.
Voert geen content-taken uit. Haalt data op en presenteert als tabel/lijst.
Onderdeel van de DIRECT_RESPONSE pipeline (geen copy_agent, geen reviewer_agent).
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class DataAgent:
    """
    Worker-agent voor data_query jobs.
    Ontvangt query_params van de CEO-orchestrator.
    Retourneert een gestructureerd data-resultaat conform het output contract.
    """

    def __init__(self, db, gsc_service=None, analytics_service=None):
        self.db = db
        self.gsc_service = gsc_service
        self.analytics_service = analytics_service

    async def execute(self, job_id: str, query_params: dict) -> dict:
        """
        Hoofdmethode. Voert de data-query uit op basis van query_params.

        Args:
            job_id: De job ID voor logging in job_steps
            query_params: {
                datasource, client_slug, site_url,
                period_days, metric, top_k
            }

        Returns:
            Output contract dict:
            {
                "gevonden": str,       # wat opgehaald, van welke bron, welke periode
                "resultaat": list,     # rijen als dicts
                "volledigheid": str,   # gaps of lege waarden
                "volgende_actie": str  # optioneel
            }
        """
        datasource = query_params.get("datasource", "gsc")
        client_slug = query_params.get("client_slug")
        site_url = query_params.get("site_url")
        period_days = query_params.get("period_days", 28)
        metric = query_params.get("metric", ["clicks", "impressions"])
        top_k = query_params.get("top_k", 10)

        await self._log_step_start(job_id, query_params)

        try:
            if datasource == "gsc":
                result = await self._query_gsc(
                    site_url=site_url,
                    period_days=period_days,
                    metric=metric,
                    top_k=top_k
                )
            elif datasource == "client_knowledge":
                result = await self._query_client_knowledge(
                    client_slug=client_slug,
                    query=query_params.get("raw_query", ""),
                    top_k=top_k
                )
            else:
                result = self._unsupported_datasource(datasource)

            await self._log_step_done(job_id)
            return result

        except Exception as e:
            logger.error(f"DataAgent.execute failed for job {job_id}: {e}")
            await self._log_step_failed(job_id, str(e))
            return self._error_result(str(e))

    async def _query_gsc(
        self,
        site_url: str,
        period_days: int,
        metric: list,
        top_k: int
    ) -> dict:
        """
        Haalt data op uit Google Search Console.
        Retourneert top_k pagina's gesorteerd op clicks (desc).
        """
        if not self.gsc_service:
            return self._unavailable_result(
                "Google Search Console",
                "GSC service niet geconfigureerd. Controleer de OAuth-koppeling."
            )

        if not site_url:
            return self._missing_param_result("site_url")

        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=period_days)

        try:
            rows = await self.gsc_service.get_top_pages(
                site_url=site_url,
                start_date=str(start_date),
                end_date=str(end_date),
                dimensions=["page"],
                metrics=metric,
                limit=top_k
            )
        except Exception as e:
            return self._unavailable_result("Google Search Console", str(e))

        if not rows:
            return {
                "gevonden": f"GSC data voor {site_url} over de afgelopen {period_days} dagen",
                "resultaat": [],
                "volledigheid": "Geen data gevonden voor deze periode. Controleer of de GSC-koppeling actief is en of er traffic is in deze periode.",
                "volgende_actie": None
            }

        return {
            "gevonden": (
                f"Top {len(rows)} pagina's uit Google Search Console "
                f"voor {site_url} — periode: {start_date} t/m {end_date} "
                f"({period_days} dagen)"
            ),
            "resultaat": rows,
            "volledigheid": self._check_completeness(rows, metric),
            "volgende_actie": f"Bekijk de volledige GSC data op Search Console voor {site_url}."
        }

    async def _query_client_knowledge(
        self,
        client_slug: str,
        query: str,
        top_k: int
    ) -> dict:
        """
        Doorzoekt de client knowledge base op basis van een tekstquery.
        Gebruikt voor vragen als 'geef mij info over onze doelgroep'.
        """
        if not client_slug:
            return self._missing_param_result("client_slug")

        try:
            rows = await self.db.fetch(
                """
                SELECT chunk_text, source_url, source_type, created_at
                FROM client_knowledge
                WHERE client_slug = $1 AND is_active = true
                ORDER BY created_at DESC
                LIMIT $2
                """,
                client_slug, top_k
            )
        except Exception as e:
            return self._unavailable_result("Client Knowledge Base", str(e))

        if not rows:
            return {
                "gevonden": f"Client knowledge base voor klant '{client_slug}'",
                "resultaat": [],
                "volledigheid": f"Geen kennisdocumenten gevonden voor klant '{client_slug}'. Voeg bronnen toe via de Kennisbronnen tab.",
                "volgende_actie": None
            }

        return {
            "gevonden": f"Top {len(rows)} kennisfragmenten voor klant '{client_slug}'",
            "resultaat": [dict(row) for row in rows],
            "volledigheid": "Resultaten gesorteerd op toegevoegdatum (nieuwste eerst). Semantische ranking is beschikbaar als BGE-M3 actief is.",
            "volgende_actie": None
        }

    def _check_completeness(self, rows: list, requested_metrics: list) -> str:
        """Controleert of de gevraagde metrics aanwezig zijn in de resultaten."""
        if not rows:
            return "Geen data."
        sample = rows[0]
        missing = [m for m in requested_metrics if m not in sample]
        if missing:
            return f"Let op: de volgende metrics ontbreken in de resultaten: {', '.join(missing)}."
        zero_values = [
            m for m in requested_metrics
            if all(row.get(m, 0) == 0 for row in rows)
        ]
        if zero_values:
            return f"De volgende metrics zijn nul voor alle resultaten: {', '.join(zero_values)}. Controleer de GSC-koppeling of de gekozen periode."
        return "Alle gevraagde metrics aanwezig."

    def _missing_param_result(self, param: str) -> dict:
        return {
            "gevonden": "Onvolledig verzoek",
            "resultaat": [],
            "volledigheid": f"Kritieke parameter ontbreekt: '{param}'. De CEO had dit moeten opvragen tijdens de intake.",
            "volgende_actie": "Herstart de job met de juiste parameters."
        }

    def _unavailable_result(self, source: str, reason: str) -> dict:
        return {
            "gevonden": f"Databron niet beschikbaar: {source}",
            "resultaat": [],
            "volledigheid": f"Kan geen data ophalen: {reason}",
            "volgende_actie": "Controleer de koppeling via Instellingen."
        }

    def _unsupported_datasource(self, datasource: str) -> dict:
        return {
            "gevonden": f"Onbekende databron: {datasource}",
            "resultaat": [],
            "volledigheid": f"Databron '{datasource}' wordt niet ondersteund. Ondersteunde bronnen: gsc, client_knowledge.",
            "volgende_actie": None
        }

    def _error_result(self, error: str) -> dict:
        return {
            "gevonden": "Fout tijdens ophalen data",
            "resultaat": [],
            "volledigheid": f"Technische fout: {error}",
            "volgende_actie": "Bekijk de backend logs voor details."
        }

    async def _log_step_start(self, job_id: str, query_params: dict):
        try:
            await self.db.execute(
                """
                INSERT INTO job_steps (job_id, agent_id, step_name, status, started_at)
                VALUES ($1, 'agent:data-analyst', 'data_retrieval', 'running', now())
                """,
                job_id
            )
        except Exception as e:
            logger.warning(f"Kon job_step niet aanmaken voor job {job_id}: {e}")

    async def _log_step_done(self, job_id: str):
        try:
            await self.db.execute(
                """
                UPDATE job_steps
                SET status = 'done', completed_at = now()
                WHERE job_id = $1 AND agent_id = 'agent:data-analyst'
                  AND status = 'running'
                """,
                job_id
            )
        except Exception as e:
            logger.warning(f"Kon job_step niet updaten voor job {job_id}: {e}")

    async def _log_step_failed(self, job_id: str, error: str):
        try:
            await self.db.execute(
                """
                UPDATE job_steps
                SET status = 'failed', error_log = $2, completed_at = now()
                WHERE job_id = $1 AND agent_id = 'agent:data-analyst'
                  AND status = 'running'
                """,
                job_id, error
            )
        except Exception as e:
            logger.warning(f"Kon job_step niet markeren als failed voor job {job_id}: {e}")
```

**Verificatie na implementatie:**
```bash
# (terminal)
python3 -c "from app.agents.data_agent import DataAgent; print('Import OK')"
```

**Stop en bevestig** dat de import slaagt voor je naar fase 4 gaat.

---

## Fase 4 — Backend: CEO routing voor data_query jobs

**Wat:** Pas de CEO-orchestrator (of `determine_next_step` functie) aan zodat jobs met `task_type = 'data_query'` de `DataAgent` aanroepen in plaats van de content pipeline.

**Bestand:** Verifieer eerst welk bestand de job routing beheert:
```bash
# (terminal)
grep -rn "determine_next_step\|copy_agent\|content_creation\|RUNNING" app/ --include="*.py" | grep -v "__pycache__"
```

### 4.1 Routing logica

Voeg de volgende routing toe aan het punt waar de CEO beslist welke agent als volgende wordt uitgevoerd:

```python
# In de CEO/orchestrator routing functie
# Lees het task_type uit de job context

job_context = json.loads(job.context) if isinstance(job.context, str) else job.context
task_type = job_context.get("detected_task_type", "content_creation")

if task_type == "data_query":
    # DIRECT_RESPONSE pipeline: DataAgent -> JOB_READY
    # Geen copy_agent, geen reviewer_agent, geen CEO approval check
    await run_data_pipeline(job_id, job_context)
    return

# Bestaande content pipeline (ongewijzigd)
await run_content_pipeline(job_id, job_context)
```

### 4.2 `run_data_pipeline` functie

Voeg toe in hetzelfde bestand of in `app/orchestrator/pipelines.py` (nieuw als dat logischer is):

```python
async def run_data_pipeline(job_id: str, job_context: dict):
    """
    Korte pipeline voor data_query jobs.
    DataAgent uitvoeren -> resultaat opslaan -> status JOB_READY.
    Geen content pipeline, geen reviewer, geen CEO approval gate.
    """
    from app.agents.data_agent import DataAgent
    # Injecteer de juiste services op basis van de bestaande service-initialisatie
    agent = DataAgent(
        db=db,  # gebruik de bestaande db-connectie
        gsc_service=get_gsc_service(job_context.get("client_slug")),
        analytics_service=None  # uitbreiden wanneer analytics koppeling live is
    )

    query_params = job_context.get("query_params", {})
    query_params["raw_query"] = job_context.get("original_query", "")

    # Status -> RUNNING
    await db.execute(
        "UPDATE jobs SET status = 'RUNNING' WHERE job_id = $1",
        job_id
    )

    # DataAgent uitvoeren
    result = await agent.execute(job_id, query_params)

    # Resultaat opslaan in context.proposed_data
    context_update = {
        **job_context,
        "proposed_data": result,
        "pipeline_type": "direct_response"
    }
    await db.execute(
        "UPDATE jobs SET context = $1, status = 'JOB_READY' WHERE job_id = $2",
        json.dumps(context_update), job_id
    )
```

### 4.3 Fallback: als `gsc_service` nog niet bestaat

Als de GSC service nog niet geïmplementeerd is, implementeer dan een stub die duidelijk aangeeft dat de koppeling ontbreekt:

```python
def get_gsc_service(client_slug: str):
    """
    Retourneert de GSC service voor een client.
    Geeft None terug als de koppeling niet beschikbaar is.
    De DataAgent handelt dit correct af met een _unavailable_result.
    """
    try:
        # Zoek de GSC OAuth token voor deze client
        # Gebruik de bestaande GSC implementatie als die bestaat
        from app.services.gsc_service import GSCService
        return GSCService(client_slug=client_slug)
    except (ImportError, Exception):
        return None  # DataAgent meldt dit expliciet aan de gebruiker
```

**Verificatie na implementatie:**
```bash
# (terminal) — restart backend en test met een data-query job
curl -X POST http://localhost:8090/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"title": "toon mij de top 10 paginas", "platform": "custom"}'
# Verwacht: job aangemaakt, detected_task_type = data_query in context
```

**Stop en bevestig** de routing werkt voor je naar fase 5 gaat.

---

## Fase 5 — Frontend: data-resultaat tonen in JOB_READY

**Wat:** Zorg dat de bestaande `ReviewDiff` of `JobDetail` component het data-resultaat correct toont als een tabel, niet als een diff-view. De content diff-view is niet van toepassing op data-query jobs.

**Aanpak:** Lees `context.pipeline_type` uit de job context. Als `pipeline_type === 'direct_response'`: toon `DataResultView`. Anders: toon de bestaande `ReviewDiff`.

**Bestand:** Verifieer eerst welk component de JOB_READY status rendert:
```bash
# (terminal)
grep -rn "JOB_READY\|ReviewDiff\|proposed_data" web_ui/frontend/src/ --include="*.jsx" --include="*.tsx"
```

### 5.1 DataResultView component (nieuw)

Maak `web_ui/frontend/src/components/DataResultView.jsx`:

```jsx
// DataResultView.jsx
// Toont het resultaat van een data_query job als gestructureerde tabel.
// Gebruikt als alternatief voor ReviewDiff wanneer pipeline_type = 'direct_response'.

import React from 'react';

export default function DataResultView({ proposedData, onApprove }) {
  if (!proposedData) {
    return <div className="p-4 text-gray-500">Geen data beschikbaar.</div>;
  }

  const { gevonden, resultaat, volledigheid, volgende_actie } = proposedData;

  return (
    <div className="space-y-4">
      {/* Bron & periode */}
      <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm text-blue-800">
        {gevonden}
      </div>

      {/* Resultaattabel */}
      {resultaat && resultaat.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100">
                {Object.keys(resultaat[0]).map((key) => (
                  <th key={key} className="border border-gray-200 px-3 py-2 text-left font-medium">
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {resultaat.map((row, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  {Object.values(row).map((val, j) => (
                    <td key={j} className="border border-gray-200 px-3 py-2">
                      {val ?? '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-gray-500 text-sm italic">Geen resultaten.</div>
      )}

      {/* Volledigheidsmelding */}
      {volledigheid && (
        <div className="text-xs text-gray-500">{volledigheid}</div>
      )}

      {/* Volgende actie */}
      {volgende_actie && (
        <div className="text-xs text-gray-400 italic">{volgende_actie}</div>
      )}

      {/* Goedkeuren knop */}
      <div className="pt-2">
        <button
          onClick={onApprove}
          className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700"
        >
          Afsluiten
        </button>
      </div>
    </div>
  );
}
```

### 5.2 Pas de JOB_READY render aan

Zoek de component die JOB_READY rendert en voeg de routing toe:

```jsx
// In het component dat JOB_READY rendert (JobDetail, ReviewDiff, of equivalent):
import DataResultView from './DataResultView';

// In de render:
const pipelineType = job?.context?.pipeline_type;
const proposedData = job?.context?.proposed_data;

if (pipelineType === 'direct_response') {
  return (
    <DataResultView
      proposedData={proposedData}
      onApprove={() => handleApprove(job.job_id)}
    />
  );
}

// Bestaande ReviewDiff voor content jobs (ongewijzigd)
return <ReviewDiff ... />;
```

**Verificatie na implementatie:**
- Maak een job aan met titel "toon mij de top 5 paginas"
- Verifieer dat de JOB_READY view een tabel toont (of een lege-state melding als GSC niet beschikbaar is), niet een diff-view.

---

## Wat je NIET doet

- Pas de content creation pipeline niet aan. `copy_agent` en `reviewer_agent` blijven ongewijzigd.
- Voeg geen nieuwe DB-status toe. `DIRECT_RESPONSE` is een intern routing-label in `job_context`, niet een waarde in de `status` kolom.
- Verwijder de `AWAITING_APPROVAL` status of CEO approval gate niet. Die blijft voor content jobs.
- Combineer de `DataAgent` niet met de `copy_agent`. Ze mogen nooit in dezelfde job-pipeline draaien.
- Maak geen aannames over de GSC service implementatie. Als `gsc_service = None`, retourneert `DataAgent` een `_unavailable_result`. Dat is correct gedrag.

---

## Acceptatiecriteria (totaal — alle fasen)

- [ ] `agent:data-analyst` bestaat in `hired_agents` met de juiste tool_whitelist
- [ ] `_detect_task_type()` retourneert `data_query` voor queries met signaalwoorden
- [ ] `_detect_task_type()` retourneert `content_creation` voor schrijfopdrachten
- [ ] Bij ontbrekende `client_slug` (meerdere clients): job gaat naar `INTAKE_CLARIFICATION` met één gerichte vraag
- [ ] Bij ontbrekende `period_days`: default 28 wordt toegepast zonder gebruikersinterruptie
- [ ] `DataAgent.execute()` retourneert het output contract (gevonden / resultaat / volledigheid / volgende_actie)
- [ ] Als GSC niet beschikbaar is: `DataAgent` retourneert een leesbare foutmelding, geen crash
- [ ] Data-query job gaat via `RUNNING -> JOB_READY` zonder `AWAITING_APPROVAL` tussenin
- [ ] Content-query job volgt de bestaande pipeline ongewijzigd
- [ ] JOB_READY view toont `DataResultView` voor data-jobs en `ReviewDiff` voor content-jobs

---

## Na elke fase

1. Laat zien wat gebouwd is (output of verificatieresultaat)
2. Zeg expliciet welke fase je hebt afgerond
3. Vraag bevestiging voor je naar de volgende fase gaat

Bij een blocker: documenteer wat er mis is en stop. Ga niet door naar de volgende fase als een verificatiestap faalt.
