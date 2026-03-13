# NEXUS — CEO Orchestrator Pipeline
## Master Plan v1.0

**Datum:** maart 2026
**Status:** Structuur geïmplementeerd — `_execute_step` en `_update_job_status` uitgebreid (retry, error_log, tokens_used, context, completed_at)
**Bestandslocatie in repo:** `docs/NEXUS_MASTER_PLAN.md`
**Relevante code:** `app/services/job_pipeline.py`, `app/orchestration/nexus_pipeline.py`

---

## 1. Wat is NEXUS?

NEXUS is de naam voor de 7-fase CEO orchestrator pipeline in Wonderz-Agentics. Het is de motor achter elke job: van het moment dat een gebruiker een opdracht indient tot het moment dat de output live gaat. NEXUS vervangt de vroegere lineaire `job_pipeline.py` logica door een gestructureerde, auditeerbare pipeline met expliciete handoffs tussen fasen, kwaliteitscontroles en een ingebouwde Dev/QA loop.

De naam staat niet voor een afkorting — het is de aanduiding van de orchestratielaag die alle agents, statussen en datastromen coördineert.

---

## 2. Kernprincipes

**Fase-isolatie:** Elke fase heeft één verantwoordelijkheid. Een fase schrijft zijn output in een `HandoffContext` dataclass en geeft die door aan de volgende fase. Geen fase leest rechtstreeks uit de database wat een vorige fase had moeten wegschrijven.

**Expliciete kwaliteitspoorten:** Tussen elke fase zit een `QualityGate`. Die gate beslist of de pipeline mag doorgaan, terug moet naar een vorige fase, of moet stoppen. Dit is de Dev/QA loop: bij falen gaat de taak terug naar de uitvoerende agent, niet naar de gebruiker.

**Token budget enforcement:** Elke fase registreert tokenverbruik. De `TokenGuard` blokkeert uitvoering zodra het jobbudget is bereikt. Geen fase mag tokens verbruiken buiten de `TokenGuard`.

**Feature flag:** NEXUS kan worden aan- en uitgezet via een feature flag (`USE_NEXUS_PIPELINE` in `.env`). Bij `USE_NEXUS_PIPELINE=false` valt de pipeline terug op de legacy `job_pipeline.py` flow. Dit maakt een veilige uitrol mogelijk.

**Observability first:** Elke fase logt zijn start, einde, tokenverbruik en uitkomst naar `job_steps`. Geen fase is een black box.

---

## 3. De 7 Fasen

```
Fase 1: INTAKE          — Analyseer de job post, stel max 3 vragen
Fase 2: BRIEF           — Bouw het StrategicBrief object
Fase 3: STRATEGY_ROOM   — Stel team samen, check hired_agents, hire indien nodig
Fase 4: EXECUTION       — Voer de stappen uit via Worker agents (Dev loop)
Fase 5: QA_REVIEW       — Talent agent valideert Worker output (QA loop)
Fase 6: CEO_CHECK       — CEO beoordeelt eindresultaat tegen originele job post
Fase 7: DEPLOY          — Approve & Deploy via UnifiedToolBridge adapter
```

### Fase 1 — INTAKE

**DB status:** `PENDING_INTAKE` → `INTAKE_CLARIFICATION`
**Verantwoordelijke class:** `IntakeEngine`
**Bestand:** `app/services/intake_engine.py`

Analyseert de ruwe job post. Als informatie ontbreekt (platform, doelgroep, KPI), stelt de CEO maximaal 3 gerichte vragen via de chat. Na beantwoording, of als de post al volledig is, sluit fase 1 af.

**HandoffContext output:**
```python
@dataclass
class IntakeHandoff:
    job_id: str
    raw_job_post: str
    clarification_answers: dict
    completeness_score: float   # 0.0 – 1.0
    is_complete: bool
```

**QualityGate 1→2:** `is_complete == True` vereist. Zo niet: terug naar gebruiker voor aanvulling. Max 2 clarificatierondes; na ronde 2 wordt `is_complete` geforceerd op `True` met assumption-based aannames.

---

### Fase 2 — BRIEF

**DB status:** `INTAKE_CLARIFICATION` → `PLAN_PROPOSED` (intern)
**Verantwoordelijke class:** `StrategyBriefBuilder`
**Bestand:** `app/services/strategy_brief.py`

Combineert de job post en de clarificatie-antwoorden tot een volledig `StrategicBrief` object. Dit object is de input voor alle volgende fasen. Geen agent na fase 2 werkt rechtstreeks met de ruwe job post.

**HandoffContext output:**
```python
@dataclass
class StrategicBrief:
    job_id: str
    objective: str
    platform: str           # shopify | wordpress | custom
    target_audience: str
    kpi: str
    tone: str
    word_count: int | None
    assumption_based: list[str]  # Aannames die niet bevestigd zijn
```

**QualityGate 2→3:** `platform` en `objective` zijn verplicht ingevuld. Ontbrekend platform: default `custom`. Ontbrekend objective: fase 2 faalt en logt als `blocked`.

---

### Fase 3 — STRATEGY_ROOM

**DB status:** `PLAN_PROPOSED`
**Verantwoordelijke class:** `StrategyRoom`
**Bestand:** `app/services/strategy_room.py`

Bepaalt welke agents nodig zijn voor de job. Controleert `hired_agents`. Als een benodigde rol ontbreekt, wordt `hire_agent()` aangeroepen (maakt een nieuwe agent aan met standaard system prompt voor die rol). Bouwt het `ExecutionPlan` als lijst van geordende stappen.

**HandoffContext output:**
```python
@dataclass
class ExecutionPlan:
    job_id: str
    steps: list[ExecutionStep]
    agents_hired: list[str]     # Nieuw aangemaakt tijdens deze fase
    estimated_tokens: int        # Schatting voor TokenGuard

@dataclass
class ExecutionStep:
    step_index: int
    agent_id: str
    agent_role: str
    description: str
    input_fields: list[str]     # Welke velden uit HandoffContext gebruikt worden
    output_field: str           # Welk veld in HandoffContext gevuld wordt
```

**QualityGate 3→4:** Alle benodigde agents beschikbaar (bestaand of nieuw aangemaakt). `estimated_tokens` binnen `token_budget`. Zo niet: `FAILED` met reden `token_budget_exceeded`.

---

### Fase 4 — EXECUTION (Dev loop)

**DB status:** `RUNNING`
**Verantwoordelijke class:** `ExecutionEngine`
**Bestand:** `app/services/execution_engine.py`

Voert de stappen uit het `ExecutionPlan` sequentieel uit. Elke stap roept de toegewezen Worker agent aan. Bij technisch falen (timeout, API error): de stap wordt maximaal 3 keer opnieuw geprobeerd binnen `_execute_step`. Na 3 mislukte pogingen: stap krijgt status `failed`, `job_steps.error_log` wordt gevuld, de job gaat naar fase 5 met een `rejection_reason`.

**Kritieke methoden:**
- `_execute_step(step, context)` — met retry max 3x en error_log in job_steps
- `_update_job_status(job_id, status, context)` — status, tokens_used, context (proposed_data / error_reason), completed_at

**HandoffContext output:**
```python
@dataclass
class ExecutionResult:
    job_id: str
    completed_steps: list[StepResult]
    failed_steps: list[StepResult]
    generated_content: str      # De primaire output (kopij, code, etc.)
    token_used: int

@dataclass
class StepResult:
    step_index: int
    agent_id: str
    status: str                 # done | failed | retrying
    output: dict
    token_usage: int
    retry_count: int
    error_log: str | None
```

**QualityGate 4→5:** Alle verplichte stappen hebben status `done`. Als een stap `failed` heeft na 3 retries: job gaat niet naar CEO_CHECK maar naar een directe `FAILED` status met het error log.

---

### Fase 5 — QA_REVIEW (QA loop)

**DB status:** `RUNNING` (intern — geen nieuwe DB status voor de gebruiker)
**Verantwoordelijke class:** `ReviewerAgent`
**Bestand:** `app/agents/reviewer_agent.py`

De Talent/Reviewer agent valideert de Worker output op kwaliteit. Controleert of de output overeenkomt met het `StrategicBrief` object (doelgroep, toon, platform, KPI). Geeft één van drie uitkomsten: `APPROVED`, `NEEDS_CHANGES` (met specifiek feedback), of `REJECTED` (na 3 rondes `NEEDS_CHANGES`).

**Maximaal 3 Dev/QA cycli:** Als de Reviewer na 3 rondes nog `NEEDS_CHANGES` geeft, wordt de job `FAILED` met reden `max_review_cycles_exceeded`. De gegenereerde content en feedback worden bewaard voor diagnose.

**HandoffContext output:**
```python
@dataclass
class QAResult:
    job_id: str
    status: str                 # APPROVED | NEEDS_CHANGES | REJECTED
    review_notes: str
    approved_content: str       # Gevuld als status == APPROVED
    feedback: str | None        # Gevuld als status == NEEDS_CHANGES
    review_cycle: int           # 1, 2, of 3
```

**QualityGate 5→6:** `QAResult.status == "APPROVED"`. Zo niet: terug naar fase 4 (Dev loop). Na 3 rondes: `FAILED`.

---

### Fase 6 — CEO_CHECK

**DB status:** `AWAITING_APPROVAL`
**Verantwoordelijke class:** `CEOReviewer`
**Bestand:** `app/agents/ceo_agent.py`

De CEO beoordeelt het eindresultaat van de Reviewer tegen de originele `StrategicBrief`. Dit is de tweede validatielaag — de CEO kijkt of het grote plaatje klopt, niet de details (dat deed de Reviewer in fase 5). Als de CEO tevreden is: job gaat naar `JOB_READY`. Niet tevreden: CEO stuurt de taak terug naar fase 4 met specifieke feedback, zonder de gebruiker te betrekken.

**Maximaal 2 CEO-terugstuurrondes.** Na 2 keer terugsturen: job gaat door naar `JOB_READY` met een CEO-notitie.

**HandoffContext output:**
```python
@dataclass
class CEOCheckResult:
    job_id: str
    status: str                 # JOB_READY | RETURN_TO_EXECUTION
    ceo_notes: str
    final_content: str
```

**QualityGate 6→7:** `CEOCheckResult.status == "JOB_READY"`. Zo niet: terug naar fase 4.

---

### Fase 7 — DEPLOY

**DB status:** `JOB_READY` → `COMPLETED`
**Verantwoordelijke class:** `DeployAgent` via `UnifiedToolBridge`
**Bestand:** `app/agents/deploy_agent.py`

Wordt pas getriggerd door de gebruiker via `POST /api/jobs/{id}/approve`. De `UnifiedToolBridge` laadt de juiste platform adapter op basis van `StrategicBrief.platform`. De adapter vertaalt de `approved_content` naar de platform-specifieke API call (Shopify, WordPress, custom). Status wordt `COMPLETED`; `jobs.completed_at` wordt gezet.

Fase 7 zet **nooit** eigenmachtig de status op `COMPLETED`. Dat doet alleen de approve endpoint op basis van expliciete gebruikersactie.

---

## 4. HandoffContext — de centrale datadrager

De `HandoffContext` dataclass bundelt alle fase-outputs in één object dat door de hele pipeline stroomt. Elke fase leest wat hij nodig heeft en schrijft zijn output terug. Geen fase communiceert via de database met een andere fase — alleen de `HandoffContext` wordt doorgegeven.

De huidige implementatie gebruikt een slankere variant (o.a. `strategic_brief` dict, `execution_plan` list). De rijke dataclasses hieronder zijn langetermijndoel.

```python
@dataclass
class HandoffContext:
    # Meta
    job_id: str
    current_phase: str
    feature_flag: str = "nexus_v1"

    # Fase 1 output
    intake: IntakeHandoff | None = None

    # Fase 2 output
    brief: StrategicBrief | None = None

    # Fase 3 output
    plan: ExecutionPlan | None = None

    # Fase 4 output
    execution: ExecutionResult | None = None

    # Fase 5 output
    qa: QAResult | None = None

    # Fase 6 output
    ceo_check: CEOCheckResult | None = None

    # Token tracking (gecumuleerd over alle fasen)
    total_tokens_used: int = 0
    token_budget: int = 50000
```

---

## 5. QualityGate protocol

Elke `QualityGate` volgt hetzelfde patroon:

```python
class QualityGate:
    def check(
        self,
        context: HandoffContext,
        phase_from: str,
        phase_to: str
    ) -> GateResult:
        ...

@dataclass
class GateResult:
    allowed: bool
    action: str         # PROCEED | RETURN | FAIL
    return_to: str | None
    reason: str | None
    log_entry: str
```

Mogelijke `action` waarden:
- `PROCEED`: pipeline gaat door naar de volgende fase
- `RETURN`: pipeline gaat terug naar `return_to` fase (Dev/QA loop)
- `FAIL`: pipeline stopt, job krijgt status `FAILED`

---

## 6. Token budget enforcement

De `TokenGuard` wordt aangeroepen door `_execute_step` voor elke LLM call en na elke stap door `_update_job_status`. De jobs-tabel gebruikt de kolom `tokens_used` (niet token_used_total) voor tracking.

```python
# Grenswaarden (conform product spec sectie 3.4)
TOKEN_BUDGET_DEFAULT  = 50_000
TOKEN_WARNING_THRESHOLD = 0.80   # 80%: CEO notificatie, pipeline gaat door
TOKEN_HARD_STOP       = 1.00    # 100%: FAILED met reden token_budget_exceeded
TOKEN_PER_STEP_LIMIT  = 10_000  # Optioneel per stap
```

---

## 7. Wat is geïmplementeerd

Per platform overzicht (maart 2026):

| Component | Status |
|-----------|--------|
| `HandoffContext` dataclass (slank) | Geïmplementeerd |
| `QualityGate` basisklasse | Geïmplementeerd |
| 7-fase pipeline klasse | Geïmplementeerd |
| Feature flag (`USE_NEXUS_PIPELINE`) | Geïmplementeerd |
| `_execute_step` (incl. retry max 3x, error_log) | Geïmplementeerd |
| `_update_job_status` (status, tokens_used, context, completed_at) | Geïmplementeerd |
| Migration job_steps.error_log, jobs.completed_at | Geïmplementeerd (069) |

---

## 8. Database en kolomnamen

- **jobs:** PK is `id` (UUID). Gebruik `id` in WHERE, niet `job_id`. Kolommen: `status`, `tokens_used`, `token_budget`, `context` (JSONB), `completed_at` (na migration 069).
- **job_steps:** Kolom voor stapduur is `timing_ms` (niet latency_ms). Bij falen: `error_log` (TEXT) vullen naast `output` (JSONB).

---

## 9. Hoe te testen

Na implementatie, voer deze verificatie queries uit:

```sql
-- Controleer of alle job_steps gevuld zijn na een test-run
SELECT step_name, status, tokens_used, retry_count, started_at, completed_at, error_log
FROM job_steps
WHERE job_id = '<test_job_id>'
ORDER BY step_index;

-- Controleer token tracking
SELECT id, status, tokens_used, token_budget,
       context->>'proposed_data' IS NOT NULL as has_content,
       completed_at
FROM jobs
WHERE id = '<test_job_id>';

-- Controleer dat NEXUS feature flag werkt
-- (in .env: USE_NEXUS_PIPELINE=true)
```

**Smoke test flow:**
1. Maak een nieuwe job aan via `POST /api/jobs`
2. Beantwoord de intake vraag via `PATCH /api/jobs/{id}/answer`
3. Keur het plan goed via `POST /api/jobs/{id}/start`
4. Poll `GET /api/jobs/{id}/status` — verwacht: status doorloopt `RUNNING` naar `JOB_READY`
5. Verifieer `job_steps` via de query hierboven
6. Keur goed via `POST /api/jobs/{id}/approve` — verwacht: `COMPLETED`, `jobs.completed_at` gezet

---

## 10. Cursor instructies

Dit bestand is de primaire referentie voor alle Cursor-werk aan de NEXUS pipeline.

**Wat Cursor wel doet:**
- `job_steps` records vullen met alle verplichte velden, inclusief `timing_ms` en `error_log` bij falen
- `HandoffContext` bijhouden als centrale datadrager
- Tokenverbruik registreren via de bestaande `TokenGuard`
- Bij status-updates: `jobs.tokens_used` en `jobs.context` (proposed_data / error_reason) en `jobs.completed_at` bij COMPLETED

**Wat Cursor niet doet:**
- De `HandoffContext` dataclass aanpassen zonder expliciete instructie
- De `QualityGate` logica omzeilen
- De fase 7 `DEPLOY` zelf triggeren (dat doet alleen de approve endpoint)
- De jobs tabel aanspreken via een kolom `job_id` — de PK is `id` (UUID)

**Deploy commando (na implementatie):**
```bash
git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build && cd ../..
```

**Migraties** worden handmatig uitgevoerd op de server:
```bash
psql "$DATABASE_URL" -f app/migrations/069_nexus_job_steps_error_log_jobs_completed_at.sql
```

---

*Laatste update: maart 2026 | Versie: 1.0*
