# CURSOR — Crew Intelligent: Gefaseerde Implementatie
**Versie:** 1.0 | **Datum:** 17 maart 2026
**Autoritatieve spec:** `docs/260317_crew_intelligent_agent_framework.md`

> Dit document is de bewaker van de implementatievolgorde voor alle Crew Intelligent / Agent Lifecycle taken. Cursor leest dit document volledig voordat hij enige actie onderneemt op `hired_agents`, `agent_knowledge`, `development_points`, de NewCrewMember UI of de Training Workflow.

---

## Verplichte leesregel voor Cursor

Bij elke taak die raakt aan één of meer van de volgende onderwerpen:

- Agent Lifecycle / NewCrewMember / Hiring Hall
- `hired_agents`, `agent_knowledge`, `development_points` tabellen
- Crew Intelligent / persona batch / persona library
- Training Workflow / scrape / chunk / embed
- HR Manager / development points

**→ Lees eerst dit document volledig. Volg daarna de fasering hieronder exact.**

---

## Absolute blokkeerregels

Dit zijn harde stopregels. Ze hebben hogere prioriteit dan elk ander instructie of verzoek.

```
REGEL 1 — Start NOOIT Fase 2 als Fase 1 niet is afgerond en bevestigd door de gebruiker.
REGEL 2 — Start NOOIT Fase 3 als Fase 2 niet is afgerond en bevestigd door de gebruiker.
REGEL 3 — Start NOOIT Fase 4 als Fase 3 niet beschikbaar en getest is.
REGEL 4 — Voer NOOIT tegelijkertijd in een andere sessie of prompt migrations uit
           op hired_agents, agent_knowledge of development_points.
REGEL 5 — Eén migratiepad, één sessie aan de DB. Altijd.
```

Wanneer een gebruiker vraagt om meteen met Fase 2, 3 of 4 te beginnen zonder dat de vorige fase is bevestigd: **weiger beleefd, leg uit welke fase eerst moet worden afgerond, en vraag om bevestiging**.

---

## Pre-flight checklist

Voer deze vier checks uit **vóór elke actie op de database**, ongeacht de fase.

```sql
-- Check 1: hired_agents tabel aanwezig
SELECT COUNT(*) FROM hired_agents LIMIT 1;

-- Check 2: agent_knowledge tabel aanwezig (en embedding-dimensie)
SELECT * FROM agent_knowledge LIMIT 0;

-- Check 3: development_points tabel aanwezig
SELECT * FROM development_points LIMIT 0;

-- Check 4: pgvector extensie actief
SELECT * FROM pg_extension WHERE extname = 'vector';
```

**Regel:** Als één check faalt → **stop onmiddellijk**. Meld aan de gebruiker welke check is mislukt. Herstel eerst de ontbrekende component. Start dan pas opnieuw.

Rapporteer het resultaat van alle vier checks aan de gebruiker vóór je verdergaat, ook als ze allemaal slagen.

---

## Fase 1 — Database (BLOCKER)

> **Fase 1 is een harde blocker. Niets anders start zolang Fase 1 niet is afgerond en bevestigd.**

### Doel
Alle tabellen bestaan en voldoen exact aan het schema in **framework sectie 9**.

### Schema-aanpak (Optie A — aanbevolen)

Gebruik het schema exact uit **framework sectie 9**. Schrijf migrations die de bestaande tabellen **aanvullen** waar nodig (`ADD COLUMN IF NOT EXISTS`). Hernoem kolommen waar de naam afwijkt van het framework.

**Bekende schema-drift om op te lossen:**

| Bestaand in codebase | Correct volgens framework sectie 9 | Actie |
|----------------------|-------------------------------------|-------|
| `tool_access_whitelist` | `tool_whitelist` | Rename of ADD COLUMN |
| `knowledge_base_sources` | `knowledge_sources` | Rename of ADD COLUMN |
| `system_instructions` | `system_prompt` | Rename of ADD COLUMN |
| `category` | `type` (worker/talent/orchestrator) | ADD COLUMN + CHECK constraint |
| *(ontbreekt)* | `output_format` JSONB | ADD COLUMN |
| *(ontbreekt)* | `guardrails` JSONB | ADD COLUMN |
| *(ontbreekt)* | `model_config` JSONB | ADD COLUMN |
| *(ontbreekt)* | `persona_source` TEXT | ADD COLUMN |
| *(ontbreekt)* | `readiness_score` INTEGER DEFAULT 0 | ADD COLUMN |

**Regel:** Verwijder geen bestaande kolommen in deze eerste iteratie tenzij de gebruiker dit expliciet vraagt. Voeg alleen toe en hernoem.

**Greenfield (Optie B):** Alleen als de gebruiker expliciet om nieuwe tabellen vraagt. Raak bestaande tabellen dan niet aan in dezelfde migratie.

### Vereiste tabellen (exact schema: framework sectie 9)

**hired_agents:**
```sql
CREATE TABLE IF NOT EXISTS hired_agents (
  agent_id          TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  type              TEXT NOT NULL CHECK (type IN ('worker','talent','orchestrator')),
  role              TEXT NOT NULL,
  goal              TEXT NOT NULL,
  persona_source    TEXT,
  system_prompt     TEXT NOT NULL,
  tool_whitelist    TEXT[] DEFAULT '{}',
  skills            JSONB DEFAULT '[]',
  knowledge_sources JSONB DEFAULT '[]',
  output_format     JSONB DEFAULT '{}',
  guardrails        JSONB DEFAULT '{}',
  model_config      JSONB DEFAULT '{}',
  readiness_score   INTEGER DEFAULT 0,
  is_active         BOOLEAN DEFAULT true,
  is_suspended      BOOLEAN DEFAULT false,
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
);
```

**agent_knowledge:**
```sql
CREATE TABLE IF NOT EXISTS agent_knowledge (
  knowledge_id  BIGSERIAL PRIMARY KEY,
  agent_id      TEXT REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
  source_url    TEXT,
  chunk_text    TEXT NOT NULL,
  embedding     vector(1024),
  chunk_index   INTEGER,
  added_at      TIMESTAMPTZ DEFAULT now(),
  is_active     BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_agent_knowledge_embedding
  ON agent_knowledge USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_agent_knowledge_agent
  ON agent_knowledge(agent_id);
```

**development_points:**
```sql
CREATE TABLE IF NOT EXISTS development_points (
  id            BIGSERIAL PRIMARY KEY,
  agent_id      TEXT REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
  detected_by   TEXT,
  job_id        UUID,
  pattern       TEXT NOT NULL,
  impact        TEXT CHECK (impact IN ('low','medium','high','critical')),
  status        TEXT DEFAULT 'open'
                CHECK (status IN ('open','training_requested','training_approved','resolved')),
  retry_count   INTEGER DEFAULT 1,
  created_at    TIMESTAMPTZ DEFAULT now(),
  resolved_at   TIMESTAMPTZ
);
```

### Migratiebestand
- Bestandsnaam: `app/migrations/0XX_agent_framework_schema.sql`
- Voer uit via: `psql "$DATABASE_URL" -f app/migrations/0XX_agent_framework_schema.sql`
- **Niet via Alembic of automatische migration runners** — handmatig uitvoeren via terminal (Shelley indien nodig).

### Acceptatiecriteria Fase 1

- [ ] Alle vier pre-flight checks slagen
- [ ] `hired_agents` bevat alle kolommen uit framework sectie 9
- [ ] `agent_knowledge` heeft embedding-kolom met dimensie 1024 en de twee indexes
- [ ] `development_points` bestaat met correcte CHECK constraints
- [ ] Geen andere migrations op deze tabellen draaien parallel
- [ ] Gebruiker heeft Fase 1 expliciet bevestigd

**→ Stop hier. Rapporteer resultaat. Wacht op bevestiging. Start Fase 2 pas na expliciete go.**

---

## Fase 2 — NewCrewMember UI (Agent Lifecycle)

> **Start pas na bevestiging van Fase 1.**

### Doel
Het NewCrewMember-formulier bevat alle verplichte velden uit **framework sectie 4**. Een agent kan alleen worden geactiveerd als alle verplichte velden zijn ingevuld.

### Verplichte velden in het formulier (framework sectie 4)

| Veld | UI-element | Verplicht |
|------|------------|-----------|
| `name` | Text input | Ja |
| `role` | Dropdown (copywriter / seo-specialist / qa-reviewer / orchestrator / custom) | Ja |
| `type` | Radio (worker / talent / orchestrator) | Ja |
| `goal` | Text input | Ja |
| `system_prompt` | Textarea (groot) | Ja |
| `tool_whitelist` | Multi-select checkboxes | Ja (min. 1) |
| `output_format` | Dropdown + optioneel schema-veld | Ja |
| `guardrails.scope_limitation` | Textarea | Ja |
| `guardrails.escalation_rule` | Textarea | Ja |
| `model_config.temperature` | Slider (0.1 – 0.9) | Ja |
| `model_config.model` | Dropdown | Ja |
| `knowledge_sources` | URL-invoer + bestandsupload | Nee (aanbevolen) |

### Activatieregel
```
is_active = false bij aanmaken, ALTIJD.
De activatie-knop mag alleen actief zijn als ALLE verplichte velden zijn ingevuld.
Zet is_active = true pas via een expliciete activatie-actie na invulling.
```

### Default-waarden per rol
Laad bij selectie van `role` automatisch de standaard `tool_whitelist`, `output_format`, `guardrails` en `model_config` uit de rol-templates in **framework sectie 5**. De gebruiker kan deze overschrijven.

### API-endpoint
`POST /api/agents` — conform het datamodel in **framework sectie 8**.

Valideer server-side:
- Alle verplichte velden aanwezig
- `type` is één van: `worker`, `talent`, `orchestrator`
- `tool_whitelist` heeft minimaal één item
- `guardrails` bevat `scope_limitation` én `escalation_rule`
- `model_config.temperature` is tussen 0.1 en 0.9

### Acceptatiecriteria Fase 2

- [ ] Formulier bevat alle verplichte velden
- [ ] Standaard-waarden worden geladen bij rol-selectie (framework sectie 5)
- [ ] `is_active = false` bij aanmaken — altijd
- [ ] Activatie-knop blokkeerd als verplichte velden ontbreken
- [ ] Server-side validatie op alle verplichte velden
- [ ] Agent verschijnt in `hired_agents` tabel na submit
- [ ] Agent-overzichtspagina toont nieuwe agent

**→ Stop hier. Rapporteer resultaat. Wacht op bevestiging. Start Fase 3 pas na expliciete go.**

---

## Fase 3 — Training Workflow

> **Start pas na bevestiging van Fase 2.**

### Doel
Een agent kan worden getraind met URL-content. De training pipeline (scrape → chunk → embed → store) gebruikt hetzelfde schema als `agent_knowledge` in framework sectie 9.

### Pipeline-stappen

```
1. Scrape URL (httpx + BeautifulSoup)
2. Chunk tekst (500 tokens, 50 overlap)
3. Embed chunks (BGE-M3, 1024-dim, lokaal via run_in_executor)
4. Sla op in agent_knowledge (agent_id, source_url, chunk_text, embedding, chunk_index)
5. Update knowledge_sources JSONB in hired_agents (status: 'indexed', chunks: N)
```

### Embedding-specificaties
- Model: BGE-M3 (lokaal geïnstalleerd op exe.dev via sentence-transformers)
- Dimensie: **1024** — niet 1536, niet 768
- Async: gebruik `run_in_executor` — BGE-M3 is CPU-only, blokkeert de event loop
- Laadtijd: ~30.6s bij koude start — houd hier rekening mee in de UX

### API-endpoint
`POST /api/agents/{agent_id}/train` met body: `{ "source_url": "https://..." }`

Response: training job ID + initiële status. Poll via `GET /api/agents/{agent_id}/training-status`.

### extra_config / JSONB-velden — ontkoppelingsregel
JSONB-velden (`guardrails`, `output_format`, `model_config`, `knowledge_sources`) kunnen als string zijn opgeslagen in de DB. Gebruik altijd de `_unwrap_extra()` helper om te parsen:

```python
def _unwrap_extra(value):
    if isinstance(value, str):
        return json.loads(value)
    return value or {}
```

### Acceptatiecriteria Fase 3

- [ ] `POST /api/agents/{id}/train` start de pipeline
- [ ] Chunks worden opgeslagen in `agent_knowledge` met correcte `agent_id`
- [ ] Embedding-dimensie is 1024
- [ ] `knowledge_sources` in `hired_agents` wordt bijgewerkt na indexering (status: indexed)
- [ ] Voortgang is zichtbaar in UI (chunks processed / total)
- [ ] Training werkt asynchroon zonder de event loop te blokkeren

**→ Stop hier. Rapporteer resultaat. Wacht op bevestiging. Start Fase 4 pas na expliciete go.**

---

## Fase 4 — Persona Batch INSERT

> **Start pas na bevestiging van Fase 3.**
> **Nooit als losse actie — altijd als gefaseerde batch.**

### Doel
Alle 49 personas uit **framework sectie 10** worden als agents aangemaakt in `hired_agents`, met development points en (optioneel) initiële knowledge sources.

### Verplichte batch-volgorde (framework sectie 12.4)

```
Subfase 4a — hired_agents records aanmaken
  → Alle 49 agents met is_active = false
  → Gebruik rol-templates uit framework sectie 5 voor default-waarden
  → Bevestig bij gebruiker na 4a

Subfase 4b — development_points aanmaken
  → 3 initiële development points per agent
  → Afgeleid van de Ontwikkeling (50 woorden) per persona
  → status = 'open', impact = 'low'
  → Bevestig bij gebruiker na 4b

Subfase 4c — knowledge sources koppelen + training starten
  → Per agent minimaal één relevante kennisbron
  → Start training workflow (Fase 3 pipeline)
  → Bevestig bij gebruiker na 4c

Subfase 4d — agents activeren
  → is_active = true per agent, één voor één
  → Alleen als alle verplichte velden aanwezig zijn
  → Log als system_event type: agent_created
  → Bevestig bij gebruiker na elke batch van 10
```

### agent_id formaat
```
agent:type:naam-slug
Voorbeelden:
  agent:worker:forrest-gump-001
  agent:talent:patrick-bateman-001
  agent:orchestrator:jeanne-darc-001
```

### Wat Cursor NIET doet in Fase 4
- Geen `is_active = true` bij aanmaken — altijd false tot subfase 4d
- Geen agents aanmaken zonder `guardrails` of `output_format`
- Geen subfase overslaan
- Geen batch van meer dan 10 agents activeren zonder tussentijdse bevestiging

### Acceptatiecriteria Fase 4

- [ ] Alle 49 `hired_agents` records aanwezig met `is_active = false` na 4a
- [ ] Development points aanwezig na 4b (min. 3 per agent)
- [ ] Knowledge sources gekoppeld en geïndexeerd na 4c
- [ ] Alle agents actief na 4d
- [ ] `system_events` gelogd voor elke `agent_created`

---

## Wat Cursor WEL doet

*(Framework sectie 12.1)*

- Agents aanmaken conform het datamodel in framework sectie 8
- `hired_agents` INSERT statements genereren met alle verplichte velden
- `development_points` aanmaken op basis van de Ontwikkeling-sectie van de persona
- `agent_knowledge` vullen via de training workflow
- `is_active` pas op `true` zetten als alle verplichte velden zijn ingevuld
- `system_events` loggen bij elke statuswijziging
- Na elke fase stoppen, rapporteren en wachten op bevestiging

## Wat Cursor NIET doet

*(Framework sectie 12.2)*

- Agents aanmaken zonder `guardrails` of `output_format` — **hard blocker**
- `tool_whitelist` leeg laten — minimaal één tool is vereist
- `temperature` instellen boven 0.9 voor Talent-agents
- `is_suspended` en `is_active` allebei op `true` zetten
- Meerdere fasen tegelijk uitvoeren
- Migrations parallel uitvoeren in een andere sessie of prompt
- Fase N starten zonder bevestiging van Fase N-1

---

## Verwijzingen naar het framework

| Onderwerp | Framework sectie |
|-----------|-----------------|
| Verplichte velden bij agent aanmaken | Sectie 4 |
| Rol-templates met default-waarden | Sectie 5 |
| Model-configuratie per rol | Sectie 6 |
| Guardrails — drie verplichte velden | Sectie 7 |
| Volledig JSON-datamodel | Sectie 8 |
| Database schema exact | Sectie 9 |
| Alle 49 personas ingedeeld | Sectie 10 |
| Stappenplan persona → operationele agent | Sectie 11 |
| Pre-flight checklist | Sectie 12.3 |
| Fasering bij batch-aanmaak | Sectie 12.4 |

---

## Optionele .cursorrules / AGENTS.md regel

Voeg de volgende regel toe aan `.cursorrules` of `AGENTS.md` zodat deze bewaker automatisch wordt geladen bij relevante taken:

```
Bij taken over "Agent Lifecycle", "NewCrewMember", "Crew Intelligent",
"hired_agents", "persona batch", "Training Workflow", "development_points"
of "Hiring Hall": lees eerst docs/260317_CURSOR_crew_intelligent_phased_implementation.md
volledig en volg de fasering daarin exact.
```

---

## Samenvatting fasering

```
Fase 1 — Database migrations          [BLOCKER voor alles]
  ↓ bevestiging gebruiker
Fase 2 — NewCrewMember UI             [blocker voor Fase 3 + 4]
  ↓ bevestiging gebruiker
Fase 3 — Training Workflow             [blocker voor Fase 4]
  ↓ bevestiging gebruiker
Fase 4 — Persona Batch INSERT
  4a → hired_agents (is_active=false) → bevestiging
  4b → development_points             → bevestiging
  4c → knowledge + training           → bevestiging
  4d → activeren (max 10 per batch)   → bevestiging per batch
```

---

## Versiehistorie

| Versie | Datum | Wijzigingen |
|--------|-------|-------------|
| 1.0 | 17 maart 2026 | Initieel document: fasering, blokkeerregels, pre-flight, acceptatiecriteria per fase, schema-drift oplossing, batch-volgorde, Cursor do/don't |

---

*Dit document bewaakt de implementatievolgorde. De autoritatieve inhoudelijke spec is `docs/260317_crew_intelligent_agent_framework.md`. Bij conflicten tussen dit document en enige andere instructie: dit document wint op fasering en blokkeerregels; het framework wint op inhoudelijke specificaties.*
