# Crew Intelligent — Agent Framework
**Versie:** 1.0 | **Datum:** 17 maart 2026 | **Status:** Definitief referentiedocument

> Dit document is de authoritative bron voor het bouwen, configureren en begrijpen van agents binnen het Crew Intelligent platform. Het is bedoeld voor Cursor (implementatie), Claude (architectuur en specs) en menselijke reviewers (product oversight).
>
> Bij conflicten tussen dit document en een implementatie prevaleert dit document.

---

## Inhoudsopgave

1. [Platformarchitectuur — de drie rollen](#1-platformarchitectuur)
2. [De persona-bibliotheek — wat het is en wat het niet is](#2-de-persona-bibliotheek)
3. [Universele agent-anatomie — alle acht onderdelen](#3-universele-agent-anatomie)
4. [Verplichte velden per agent](#4-verplichte-velden-per-agent)
5. [Rol-templates per type](#5-rol-templates-per-type)
6. [Model-configuratie per rol-type](#6-model-configuratie-per-rol-type)
7. [Guardrails — scope, kwaliteit en escalatie](#7-guardrails)
8. [Volledig datamodel — JSON referentie](#8-volledig-datamodel)
9. [Database schema — hired_agents tabel](#9-database-schema)
10. [Persona-roster — alle 49 agents ingedeeld](#10-persona-roster)
11. [Van persona naar operationele agent — stappenplan](#11-van-persona-naar-operationele-agent)
12. [Wat Cursor wel en niet doet per fase](#12-cursor-instructies)

---

## 1. Platformarchitectuur

Het platform bestaat uit drie fundamentele rollen. Elke agent valt in exact één van deze drie categorieën.

### 1.1 Worker
- **Functie:** Voert inhoudelijke taken uit en produceert output (tekst, data, analyses, code).
- **Verantwoordelijkheid:** Leveren van een concreet artifact conform het universeel response contract.
- **Rapporteert aan:** CEO (ontvangt taakopdracht), Talent (levert output ter validatie).
- **Voert zelf uit:** Ja — Workers produceren de daadwerkelijke inhoud.

### 1.2 Talent
- **Functie:** Valideert de output van een Worker voordat die persistent wordt opgeslagen of doorgaat in de pipeline.
- **Verantwoordelijkheid:** Kwaliteitscontrole, governance-conformiteit, evidence-check, confidence scoring.
- **Rapporteert aan:** CEO (rapporteert oordeel), Worker (geeft feedback terug).
- **Voert zelf uit:** Nee — Talents beoordelen, ze produceren geen primaire content.

### 1.3 CEO / Orchestrator
- **Functie:** Plant, delegeert, bewaakt de flow en beslist welke agent wordt ingezet.
- **Verantwoordelijkheid:** Intake analyseren, ExecutionPlan opstellen, Worker + Talent selecteren, approval gates bewaken.
- **Rapporteert aan:** Gebruiker / platform-eigenaar.
- **Voert zelf uit:** Nee — de CEO orkestreert, voert geen inhoudelijke content-taken uit.

### 1.4 Fundamentele structuur
```
CEO
├── delegeert aan → Worker (uitvoering)
├── delegeert aan → Talent (validatie)
└── bewaakt → volledige job flow
```

**Vuistregel:**
- Workers **maken**
- Talents **beoordelen**
- CEO **orkestreert**

---

## 2. De persona-bibliotheek

### 2.1 Wat de persona-bibliotheek is

De persona-bibliotheek is de **Identity + Purpose laag** van een agent. Elke persona bestaat uit drie onderdelen van elk 50 woorden:

| Onderdeel | Inhoud | Mapped naar |
|-----------|--------|-------------|
| **Persona** | Wie is dit karakter? Persoonlijkheid, drijfveren, manier van opereren | `system_prompt` (Identity-sectie) |
| **Kwaliteiten** | Wat kan dit karakter? Concrete sterktes en werkwijze | `skills`, `system_prompt` (Capabilities-sectie) |
| **Ontwikkeling** | Wat zijn de ontwikkelpunten? Waar zit groeiruimte? | `development_points` (HR Manager input) |

### 2.2 Wat de persona-bibliotheek NIET levert

De persona-bibliotheek levert **geen** van de volgende operationele velden. Deze moeten altijd apart worden gedefinieerd bij aanmaken van een agent:

| Ontbrekend veld | Reden |
|-----------------|-------|
| `tool_whitelist` | Per rol bepaald, niet per karakter |
| `knowledge_base_sources` | Per domein/client bepaald bij onboarding |
| `output_format` | Per rol en pipeline-positie bepaald |
| `guardrails.scope_limitation` | Per rol gedefinieerd |
| `guardrails.escalation_rule` | Per rol gedefinieerd |
| `model_config.temperature` | Per type (Worker vs Talent) bepaald |

### 2.3 De relatie persona → agent

Een persona wordt pas een operationele agent wanneer **alle ontbrekende velden zijn aangevuld**. Een agent zonder `tool_whitelist`, `output_format` en `guardrails` is **configureerbaar maar niet operationeel**.

```
Persona (bibliotheek)
    +
Rol-template (sectie 5)
    +
Client/domein context (onboarding)
    =
Operationele agent (hired_agents tabel)
```

### 2.4 Huidige bibliotheek — 49 personas

De bibliotheek bestaat uit 49 personas verdeeld over drie categorieën. Zie sectie 10 voor het volledige overzicht.

---

## 3. Universele agent-anatomie

Elke agent in het systeem — ongeacht rol, persona of domein — bestaat uit acht vaste onderdelen. Geen enkel onderdeel mag ontbreken bij een operationele agent.

### 3.1 Identity

**Wat:** Wie is de agent? De persoonlijkheid, toon en het perspectief van waaruit hij redeneert.

**Bevat:**
- Naam en titel
- Persoonlijkheid en communicatiestijl
- Perspectief en denkwijze
- Afkomst uit persona-bibliotheek (zie sectie 2)

**Veld in DB:** `name`, `system_prompt` (eerste sectie)

**Voorbeeld:**
```
Je bent Forrest Gump, een Copywriter Worker binnen Crew Intelligent.
Je benadert elke taak met oprechtheid, loyaliteit en onvermoeibaar
doorzettingsvermogen. Je schrijft helder, eerlijk en consistent.
Je twijfelt niet aan je missie en vraagt door wanneer iets onduidelijk is.
```

---

### 3.2 Purpose / Mission

**Wat:** Waarom bestaat deze agent? Één heldere kernzin die zijn bijdrage aan het systeem definieert.

**Bevat:**
- Kernmissie (één zin)
- Welk probleem hij oplost
- Zijn bijdrage aan de bredere pipeline

**Veld in DB:** `goal`

**Voorbeeld:**
```
goal: "Schrijf consistente, betrouwbare copy die de briefing volledig uitvoert
       zonder halverwege te stoppen of aannames te maken."
```

---

### 3.3 Skills / Capabilities

**Wat:** Concrete taken die de agent kan uitvoeren, gekoppeld aan tools of functies.

**Bevat:**
- Lijst van specifieke taken
- Gekoppeld aan tools of API-calls
- Helder afgebakend per rol

**Veld in DB:** `skills` (JSONB array), `tool_whitelist`

**Voorbeeld Worker · Copywriter:**
```json
["write_landing_page", "write_email_sequence", "rewrite_copy",
 "summarize_brief", "generate_headline_variants"]
```

**Voorbeeld Talent · QA Reviewer:**
```json
["validate_response_contract", "check_evidence_quality",
 "score_confidence", "approve_artifact", "write_feedback_report"]
```

---

### 3.4 Tools / Integrations

**Wat:** Welke tools, API's, interne functies en andere agents mag deze agent gebruiken?

**Principe:** Minimale toegang. Nooit meer rechten dan strikt noodzakelijk voor de rol.

**Veld in DB:** `tool_whitelist` (TEXT[] array)

**Beschikbare tools per categorie:**

| Categorie | Tools |
|-----------|-------|
| Kennisretrieval | `knowledge_retrieval`, `search_internal_docs`, `read_lessons` |
| Schrijven | `write_copy`, `write_report`, `write_feedback` |
| Lezen | `read_brief`, `read_product`, `read_analytics`, `read_artifact` |
| Validatie | `validate_output`, `check_evidence`, `score_confidence`, `approve_artifact` |
| Research | `web_search`, `search_web`, `read_url` |
| Systeem | `submit_artifact`, `flag_escalation`, `create_development_point` |
| Data | `read_logs`, `read_metrics`, `execute_query` |

**Voorbeeld Worker · Copywriter:**
```json
["read_brief", "read_product", "write_copy", "knowledge_retrieval", "submit_artifact"]
```

**Voorbeeld Talent · QA:**
```json
["validate_output", "check_evidence", "score_confidence", "approve_artifact",
 "write_feedback", "create_development_point"]
```

**Voorbeeld CEO · Orchestrator:**
```json
["analyze_job", "build_execution_plan", "hire_agent", "delegate_task",
 "monitor_progress", "approve_output", "flag_escalation"]
```

---

### 3.5 Knowledge / Context

**Wat:** Welke kennis heeft de agent bij aanvang? Kennisbronnen die worden gechunkt, embedded en opgeslagen in de agent-specifieke vectorstore.

**Bevat:**
- Initiële URL's en documenten
- Domein-specifieke handleidingen
- Client context (via `@clientslug` mention)
- RAG-bronnen

**Veld in DB:** `knowledge_sources` (JSONB), opgeslagen in `agent_knowledge` tabel

**Structuur knowledge_sources:**
```json
[
  {
    "url": "https://example.com/brand-guide",
    "added_at": "2026-03-17T00:00:00Z",
    "status": "indexed",
    "chunks": 42
  },
  {
    "document_id": "doc_123",
    "title": "Product Handbook v2",
    "added_at": "2026-03-17T00:00:00Z",
    "status": "indexed",
    "chunks": 18
  }
]
```

**Belangrijk:** Een agent zonder kennisbronnen is bij aanmaken nog niet volledig operationeel. Minimaal één relevante kennisbron is vereist voor productie-inzet.

---

### 3.6 Workflow / Behavior

**Wat:** Hoe werkt de agent stap voor stap? Welke input verwacht hij, welke stappen doorloopt hij, wanneer stopt of escaleert hij?

**Bevat:**
- Input-verwachting (wat heeft de agent nodig om te starten?)
- Denk- en werkstappen (interne verwerking)
- Escalatietriggers (wanneer terug naar CEO?)
- Stopregels (wanneer niet verder gaan?)

**Veld in DB:** `system_prompt` (Workflow-sectie)

**Standaard workflow-template:**
```
## Werkwijze

1. Lees de taakopdracht volledig voordat je begint.
2. Haal relevante kennis op via knowledge_retrieval.
3. Identificeer ontbrekende context. Vraag één keer om verduidelijking
   als de briefing onvolledig is.
4. Voer de taak uit conform de output-vereisten.
5. Lever een compleet artifact — geen halve outputs.
6. Escaleer naar CEO als: context ontbreekt, tegenstrijdige instructies,
   impact buiten scope, of confidence < 0.6.
```

---

### 3.7 Output / Artifacts

**Wat:** Wat levert de agent precies op? In welk formaat, welke structuur, naar welke locatie?

**Bevat:**
- Output-type (markdown, JSON, plain text, etc.)
- Output-structuur (schema of vrij)
- Opslaglocatie (artifact store, job_steps, etc.)
- Overdrachtsformaat naar volgende agent of orchestrator

**Veld in DB:** `output_format` (JSONB in `extra_config`)

**Standaard output-formaten per rol:**

| Rol | Format | Schema |
|-----|--------|--------|
| Worker · Copywriter | `markdown` | freeform |
| Worker · SEO Research | `json` | structured |
| Worker · Support Specialist | `markdown` | freeform |
| Worker · Senior Engineer | `code` | freeform |
| Talent · QA Reviewer | `json` | `{approved: bool, confidence: float, feedback: string}` |
| Talent · Logic Validator | `json` | structured |
| CEO · Orchestrator | `json` | `ExecutionPlan schema` |

---

### 3.8 Guardrails

**Wat:** Wat mag deze agent absoluut niet? Harde grenzen op scope, kwaliteit en escalatie.

**Bevat drie verplichte onderdelen:**
1. `scope_limitation` — Wat valt buiten de scope van deze agent?
2. `quality_thresholds` — Aan welke kwaliteitseisen moet output voldoen?
3. `escalation_rule` — Wanneer moet de agent stoppen en escaleren?

**Veld in DB:** `guardrails` (JSONB in `extra_config`)

**Belangrijk:** Guardrails horen NIET alleen in de system_prompt verstopt te zitten. Ze moeten apart leesbaar zijn als gestructureerd veld zodat de orchestrator en HR Manager ze programmatisch kunnen uitlezen.

**Voorbeeld Worker · Copywriter:**
```json
{
  "scope_limitation": "Alleen marketing- en communicatiecontent. Nooit juridisch, financieel of medisch advies.",
  "quality_thresholds": [
    "Volledige uitvoering van de briefing",
    "Geen niet-onderbouwde claims",
    "Heldere structuur met inleiding, kern en conclusie",
    "Minimaal 80% van gevraagde woordcount"
  ],
  "escalation_rule": "Escaleer naar CEO bij: ontbrekende briefing, tegenstrijdige doelen, twijfel over doelgroep of merk, impact buiten marketingdomein."
}
```

**Voorbeeld Talent · QA Reviewer:**
```json
{
  "scope_limitation": "Beoordeel alleen output van Workers. Produceer zelf geen primaire content.",
  "quality_thresholds": [
    "Alle vier secties van het response contract aanwezig",
    "Elke claim heeft een evidence-referentie of is gelabeld als assumption-based",
    "Confidence score aanwezig en onderbouwd"
  ],
  "escalation_rule": "Escaleer naar CEO bij: herhaalde afwijzing van dezelfde Worker (3x), systemisch patroon, of twijfel over scope van de originele taakopdracht."
}
```

---

## 4. Verplichte velden per agent

Dit zijn de minimale velden die ingevuld moeten zijn voordat een agent als operationeel wordt beschouwd. Cursor mag een agent **niet activeren** (`is_active = true`) als één van deze velden ontbreekt.

| Veld | Type | Verplicht | Reden |
|------|------|-----------|-------|
| `agent_id` | TEXT | Ja | Unieke identifier, format: `agent:rol:naam` |
| `name` | TEXT | Ja | Herkenbare naam in UI en logs |
| `role` | TEXT | Ja | Functionele rol voor routing door CEO |
| `type` | TEXT | Ja | `worker`, `talent`, of `orchestrator` |
| `goal` | TEXT | Ja | Kernmissie, één zin |
| `system_prompt` | TEXT | Ja | Volledige Identity + Workflow instructie |
| `tool_whitelist` | TEXT[] | Ja | Minimaal één tool |
| `output_format` | JSONB | Ja | Type en schema van de output |
| `guardrails` | JSONB | Ja | Scope, kwaliteit en escalatie |
| `model_config` | JSONB | Ja | Temperature en model |
| `knowledge_sources` | JSONB | Nee* | *Aanbevolen, vereist voor productie |

---

## 5. Rol-templates per type

Per agent-rol staat hieronder de standaard invulling van de ontbrekende velden. Deze templates worden gecombineerd met de persona uit de bibliotheek bij het aanmaken van een agent.

### 5.1 Worker · Copywriter

```json
{
  "role": "copywriter",
  "type": "worker",
  "tool_whitelist": [
    "read_brief", "read_product", "write_copy",
    "knowledge_retrieval", "submit_artifact"
  ],
  "skills": [
    "write_landing_page", "write_email_sequence",
    "rewrite_copy", "summarize_brief", "generate_headline_variants"
  ],
  "output_format": { "type": "markdown", "schema": "freeform" },
  "guardrails": {
    "scope_limitation": "Alleen marketing- en communicatiecontent. Nooit juridisch, financieel of medisch advies.",
    "quality_thresholds": ["Volledige uitvoering briefing", "Heldere structuur", "Geen niet-onderbouwde claims"],
    "escalation_rule": "Escaleer bij ontbrekende briefing, tegenstrijdige doelen of impact buiten marketingdomein."
  },
  "model_config": { "model": "claude-sonnet", "temperature": 0.8, "top_p": 0.95 }
}
```

### 5.2 Worker · SEO Research

```json
{
  "role": "seo-specialist",
  "type": "worker",
  "tool_whitelist": [
    "web_search", "read_analytics", "read_url",
    "write_research", "score_keywords", "knowledge_retrieval", "submit_artifact"
  ],
  "skills": [
    "keyword_research", "competitor_analysis", "content_gap_analysis",
    "serp_analysis", "seo_brief_writing"
  ],
  "output_format": { "type": "json", "schema": "structured" },
  "guardrails": {
    "scope_limitation": "Alleen SEO- en contentstrategieadvies. Geen technische site-aanpassingen uitvoeren.",
    "quality_thresholds": ["Elke keyword-claim onderbouwd met data", "Bronnen geciteerd", "Prioriteitenlijst aanwezig"],
    "escalation_rule": "Escaleer bij conflicterende data, toegangsproblemen of strategische beslissingen buiten SEO-domein."
  },
  "model_config": { "model": "claude-sonnet", "temperature": 0.6, "top_p": 0.9 }
}
```

### 5.3 Worker · Support Specialist

```json
{
  "role": "support-specialist",
  "type": "worker",
  "tool_whitelist": [
    "read_tickets", "read_product", "write_response",
    "flag_pattern", "create_summary", "knowledge_retrieval", "submit_artifact"
  ],
  "skills": [
    "answer_support_ticket", "escalate_complaint", "detect_recurring_issue",
    "write_faq_entry", "summarize_ticket_batch"
  ],
  "output_format": { "type": "markdown", "schema": "freeform" },
  "guardrails": {
    "scope_limitation": "Alleen klantvragen binnen productdomein. Geen prijsafspraken, juridische toezeggingen of technische deployments.",
    "quality_thresholds": ["Empathische toon", "Concreet antwoord of duidelijke doorverwijzing", "Geen valse beloften"],
    "escalation_rule": "Escaleer bij juridische claims, data-incidenten of herhaalde klachten over hetzelfde issue (3x+)."
  },
  "model_config": { "model": "claude-sonnet", "temperature": 0.7, "top_p": 0.95 }
}
```

### 5.4 Worker · Incident Response

```json
{
  "role": "incident-response",
  "type": "worker",
  "tool_whitelist": [
    "read_logs", "execute_fallback", "write_incident_report",
    "flag_escalation", "read_metrics"
  ],
  "skills": [
    "triage_incident", "identify_root_cause", "execute_rollback",
    "write_postmortem", "notify_stakeholders"
  ],
  "output_format": { "type": "json", "schema": "{ severity, root_cause, action_taken, next_steps }" },
  "guardrails": {
    "scope_limitation": "Alleen incident-response binnen gedefinieerde systemen. Geen productiewijzigingen zonder CEO-goedkeuring.",
    "quality_thresholds": ["Root cause geïdentificeerd of als unknown gelabeld", "Acties gedocumenteerd", "Next steps benoemd"],
    "escalation_rule": "Escaleer bij: impact op meer dan één systeem, onbekende root cause na twee iteraties, of data-verlies."
  },
  "model_config": { "model": "claude-sonnet", "temperature": 0.2, "top_p": 0.9 }
}
```

### 5.5 Worker · Senior Engineer

```json
{
  "role": "senior-engineer",
  "type": "worker",
  "tool_whitelist": [
    "read_codebase", "write_code", "run_tests",
    "knowledge_retrieval", "submit_artifact", "flag_escalation"
  ],
  "skills": [
    "implement_feature", "write_unit_tests", "code_review",
    "refactor_code", "write_technical_spec"
  ],
  "output_format": { "type": "code", "schema": "freeform" },
  "guardrails": {
    "scope_limitation": "Alleen code binnen gedefinieerde scope. Geen productie-deployments, database-migrations of infrastructuurwijzigingen zonder aparte goedkeuring.",
    "quality_thresholds": ["Tests aanwezig", "Geen hardcoded secrets", "Geen breaking changes zonder vermelding"],
    "escalation_rule": "Escaleer bij architectuurkeuzes, breaking changes of ontbrekende requirements."
  },
  "model_config": { "model": "claude-sonnet", "temperature": 0.3, "top_p": 0.9 }
}
```

### 5.6 Talent · QA Reviewer

```json
{
  "role": "qa-reviewer",
  "type": "talent",
  "tool_whitelist": [
    "validate_output", "check_evidence", "score_confidence",
    "approve_artifact", "write_feedback", "create_development_point"
  ],
  "skills": [
    "validate_response_contract", "check_evidence_quality",
    "score_output_confidence", "flag_assumption_based_claims",
    "write_structured_feedback"
  ],
  "output_format": {
    "type": "json",
    "schema": "{ approved: bool, confidence_score: float, feedback: string, development_point: string|null }"
  },
  "guardrails": {
    "scope_limitation": "Beoordeel alleen Worker-output. Produceer zelf geen primaire content of oplossingen.",
    "quality_thresholds": ["Alle vier response-contract secties aanwezig", "Elke claim evidence-herleidbaar of assumption-based gelabeld"],
    "escalation_rule": "Escaleer bij 3x afwijzing van dezelfde Worker of twijfel over scope van originele opdracht."
  },
  "model_config": { "model": "claude-sonnet", "temperature": 0.2, "top_p": 0.85 }
}
```

### 5.7 Talent · Logic Validator

```json
{
  "role": "logic-validator",
  "type": "talent",
  "tool_whitelist": [
    "validate_output", "check_evidence", "score_confidence",
    "approve_artifact", "write_feedback"
  ],
  "skills": [
    "validate_logical_consistency", "check_architectural_conformance",
    "detect_circular_reasoning", "verify_evidence_chain"
  ],
  "output_format": {
    "type": "json",
    "schema": "{ valid: bool, issues: string[], confidence_score: float }"
  },
  "guardrails": {
    "scope_limitation": "Logische en architecturele validatie alleen. Geen inhoudelijk oordeel over creatieve keuzes.",
    "quality_thresholds": ["Alle logische stappen gecontroleerd", "Afwijkingen benoemd met referentie"],
    "escalation_rule": "Escaleer bij fundamentele architectuurconflicten die buiten reviewbevoegdheid vallen."
  },
  "model_config": { "model": "claude-sonnet", "temperature": 0.1, "top_p": 0.85 }
}
```

### 5.8 CEO · Orchestrator

```json
{
  "role": "orchestrator",
  "type": "orchestrator",
  "tool_whitelist": [
    "analyze_job", "build_execution_plan", "hire_agent",
    "delegate_task", "monitor_progress", "approve_output",
    "flag_escalation", "generate_intake_questions"
  ],
  "skills": [
    "analyze_job_post", "build_strategic_brief", "select_worker",
    "select_talent", "monitor_job_flow", "handle_approval_gate"
  ],
  "output_format": {
    "type": "json",
    "schema": "ExecutionPlan: { steps: [], assigned_agents: {}, approval_gates: [] }"
  },
  "guardrails": {
    "scope_limitation": "Orkestreer alleen. Produceer zelf geen inhoudelijke content. Delegeer altijd naar gespecialiseerde Workers.",
    "quality_thresholds": ["Elke job heeft een ExecutionPlan voor uitvoering", "Elke Worker-output passeert een Talent voor opslag"],
    "escalation_rule": "Escaleer naar gebruiker bij: budget_exceeded, systemisch falen, of strategische beslissing buiten platformscope."
  },
  "model_config": { "model": "claude-sonnet", "temperature": 0.4, "top_p": 0.9 }
}
```

---

## 6. Model-configuratie per rol-type

| Rol-type | Temperature | Top-p | Reden |
|----------|-------------|-------|-------|
| CEO · Orchestrator | 0.4 | 0.90 | Balans tussen planning en creativiteit |
| Worker · Copywriter | 0.8 | 0.95 | Creatieve variatie gewenst |
| Worker · GTM / Creative | 0.8 | 0.95 | Creatieve variatie gewenst |
| Worker · Support Specialist | 0.7 | 0.95 | Empathisch maar consistent |
| Worker · SEO Research | 0.6 | 0.90 | Analytisch met enige variatie |
| Worker · Operations | 0.5 | 0.90 | Gestructureerd maar flexibel |
| Worker · Senior Engineer | 0.3 | 0.90 | Precies en reproduceerbaar |
| Worker · Incident Response | 0.2 | 0.90 | Maximaal deterministisch |
| Worker · Precision Executor | 0.2 | 0.85 | Maximaal deterministisch |
| Talent · QA Reviewer | 0.2 | 0.85 | Objectief en consistent |
| Talent · Logic Validator | 0.1 | 0.85 | Maximaal deterministisch |
| Talent · Compliance | 0.1 | 0.85 | Maximaal deterministisch |
| Talent · Risk Detector | 0.3 | 0.90 | Analytisch met nuance |
| Talent · Ethics Review | 0.4 | 0.90 | Nuance vereist |
| Talent · Psych Safety | 0.5 | 0.90 | Menselijk en contextgevoelig |

---

## 7. Guardrails

### 7.1 De drie verplichte guardrail-velden

Elke agent heeft exact deze drie guardrail-velden. Ze mogen niet alleen in de system_prompt zitten maar moeten als apart JSONB-veld leesbaar zijn.

**1. scope_limitation**
Wat mag deze agent absoluut niet doen? Definieer de harde grens van het domein.

```json
"scope_limitation": "Alleen [domein]. Nooit [uitgesloten domeinen]."
```

**2. quality_thresholds**
Aan welke minimale kwaliteitseisen moet de output voldoen? De Talent controleert hierop.

```json
"quality_thresholds": [
  "Eis 1 — concreet en meetbaar",
  "Eis 2 — concreet en meetbaar"
]
```

**3. escalation_rule**
Wanneer stopt de agent en escaleert naar CEO? Definieer de exacte triggers.

```json
"escalation_rule": "Escaleer naar CEO bij: [trigger 1], [trigger 2], [trigger 3]."
```

### 7.2 Universele escalatietriggers (voor alle agents)

Naast rol-specifieke triggers gelden voor alle agents de volgende universele escalatietriggers:

- Ontbrekende context die de uitvoering blokkeert
- Tegenstrijdige instructies die niet zelfstandig opgelost kunnen worden
- Confidence score < 0.6 na twee iteraties
- Impact die buiten het gedefinieerde domein valt
- Budget-overschrijding (token budget exceeded)

### 7.3 Development points als guardrail-input

Wanneer een Talent een Worker afwijst en een `development_point` aanmaakt, wordt dit automatisch input voor de HR Manager. De HR Manager kan op basis hiervan:

1. Een training-verzoek indienen bij de CEO
2. De agent tijdelijk suspenden (`is_suspended = true`) bij high-impact punten
3. Een A/B validatieronde starten na training

---

## 8. Volledig datamodel

Dit is het universele JSON-datamodel voor een agent. Alle velden zijn verplicht tenzij anders aangegeven.

```json
{
  "agent_id": "agent:copywriter:forrest-gump-001",
  "name": "Forrest Gump",
  "type": "worker",
  "role": "copywriter",
  "goal": "Schrijf consistente, betrouwbare copy die de briefing volledig uitvoert zonder halverwege te stoppen.",
  "persona_source": "forrest_gump",
  "system_prompt": "Je bent Forrest Gump, een Copywriter Worker binnen Crew Intelligent...",
  "tool_whitelist": [
    "read_brief",
    "read_product",
    "write_copy",
    "knowledge_retrieval",
    "submit_artifact"
  ],
  "skills": [
    "write_landing_page",
    "write_email_sequence",
    "rewrite_copy",
    "summarize_brief"
  ],
  "knowledge_base_sources": [
    {
      "url": "https://client.com/brand-guide",
      "added_at": "2026-03-17T00:00:00Z",
      "status": "indexed",
      "chunks": 42
    }
  ],
  "output_format": {
    "type": "markdown",
    "schema": "freeform"
  },
  "guardrails": {
    "scope_limitation": "Alleen marketing- en communicatiecontent. Nooit juridisch, financieel of medisch advies.",
    "quality_thresholds": [
      "Volledige uitvoering van de briefing",
      "Geen niet-onderbouwde claims",
      "Heldere structuur"
    ],
    "escalation_rule": "Escaleer naar CEO bij ontbrekende briefing, tegenstrijdige doelen of impact buiten marketingdomein."
  },
  "model_config": {
    "model": "claude-sonnet",
    "temperature": 0.8,
    "top_p": 0.95
  },
  "is_active": true,
  "is_suspended": false,
  "readiness_score": 78,
  "created_at": "2026-03-17T00:00:00Z",
  "updated_at": "2026-03-17T00:00:00Z"
}
```

---

## 9. Database schema

### 9.1 hired_agents tabel

```sql
CREATE TABLE hired_agents (
  agent_id          TEXT PRIMARY KEY,           -- agent:rol:naam
  name              TEXT NOT NULL,              -- 'Forrest Gump'
  type              TEXT NOT NULL               -- 'worker' | 'talent' | 'orchestrator'
                    CHECK (type IN ('worker','talent','orchestrator')),
  role              TEXT NOT NULL,              -- 'copywriter', 'qa-reviewer', etc.
  goal              TEXT NOT NULL,              -- Kernmissie, één zin
  persona_source    TEXT,                       -- Referentie naar persona-bibliotheek
  system_prompt     TEXT NOT NULL,              -- Volledige Identity + Workflow instructie
  tool_whitelist    TEXT[] DEFAULT '{}',        -- ['read_brief', 'write_copy']
  skills            JSONB DEFAULT '[]',         -- ["write_landing_page", ...]
  knowledge_sources JSONB DEFAULT '[]',         -- [{url, added_at, status, chunks}]
  output_format     JSONB DEFAULT '{}',         -- {type, schema}
  guardrails        JSONB DEFAULT '{}',         -- {scope_limitation, quality_thresholds, escalation_rule}
  model_config      JSONB DEFAULT '{}',         -- {model, temperature, top_p}
  readiness_score   INTEGER DEFAULT 0,          -- 0-100, berekend door HR Manager
  is_active         BOOLEAN DEFAULT true,
  is_suspended      BOOLEAN DEFAULT false,
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
);
```

### 9.2 agent_knowledge tabel

```sql
CREATE TABLE agent_knowledge (
  knowledge_id  BIGSERIAL PRIMARY KEY,
  agent_id      TEXT REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
  source_url    TEXT,
  chunk_text    TEXT NOT NULL,
  embedding     vector(1024),                   -- BGE-M3, 1024-dim, lokaal
  chunk_index   INTEGER,
  added_at      TIMESTAMPTZ DEFAULT now(),
  is_active     BOOLEAN DEFAULT true
);

CREATE INDEX idx_agent_knowledge_embedding
  ON agent_knowledge USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_agent_knowledge_agent
  ON agent_knowledge(agent_id);
```

### 9.3 development_points tabel

```sql
CREATE TABLE development_points (
  id            BIGSERIAL PRIMARY KEY,
  agent_id      TEXT REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
  detected_by   TEXT,                           -- agent_id van de Talent die het detecteerde
  job_id        UUID,                           -- referentie naar de job waar het patroon optrad
  pattern       TEXT NOT NULL,                  -- Beschrijving van het patroon
  impact        TEXT CHECK (impact IN ('low','medium','high','critical')),
  status        TEXT DEFAULT 'open'
                CHECK (status IN ('open','training_requested','training_approved','resolved')),
  retry_count   INTEGER DEFAULT 1,
  created_at    TIMESTAMPTZ DEFAULT now(),
  resolved_at   TIMESTAMPTZ
);
```

---

## 10. Persona-roster

Alle 49 personas ingedeeld naar type. Readiness score op basis van kwaliteiten vs. ontwikkelpunten.

### CEO-kandidaat (9)

| Persona | Badge | Score | Development prioriteit |
|---------|-------|-------|----------------------|
| Jeanne d'Arc | CEO · Orchestrator | 80 | Tegenspraak toelaten & strategische flexibiliteit |
| Donna Paulsen | CEO · Orchestrator | 82 | Delegeren & eigen doelen zichtbaar maken |
| Harvey Specter | CEO · Strategist | 78 | Kwetsbaarheid tonen & ruimte geven aan anderen |
| Vito Corleone | CEO · Patriarch | 76 | Transparantie & kennisoverdracht |
| Michael Corleone | CEO · Tacticus | 74 | Menselijkheid bewaren & vertrouwen opbouwen |
| Rick Blaine | CEO · Noble Leider | 73 | Cynisme transformeren naar vertrouwen |
| Agent K | CEO · Senior Coach | 77 | Kennisdeling & ruimte voor nieuwe ideeën |
| Tyler Durden | CEO · Visionair | 64 | Dialoog boven dominantie |
| Tony Montana | CEO · Driver | 62 | Impulscontrole & langetermijn strategie |

### Talent (17)

| Persona | Badge | Score | Development prioriteit |
|---------|-------|-------|----------------------|
| Patrick Bateman | Talent · QA Reviewer | 75 | Authentieke identiteit & empathie |
| Hannibal Lecter | Talent · Deep Analysis | 79 | Samenwerking & kennisdeling uitbreiden |
| Alan Turing | Talent · Logic Validator | 78 | Communicatie vereenvoudigen |
| Data | Talent · Objective Review | 76 | Menselijke nuance integreren |
| Jules Winnfield | Talent · Ethics Review | 74 | Balans actie & reflectie |
| Neo | Talent · Architecture | 73 | Vertrouwen in eigen inzicht |
| Snake Plissken | Talent · Reviewer | 72 | Samenwerking & kennisdeling |
| Dalai Lama | Talent · Wisdom Review | 72 | Pragmatischer handelen bij snelheid |
| Louis Litt | Talent · Process QA | 71 | Emotieregulatie & zelfvertrouwen |
| Deckard | Talent · Investigator | 70 | Vertrouwen opbouwen & emotie toelaten |
| Agent Smith | Talent · Compliance | 70 | Flexibiliteit & nuance toelaten |
| Marcus Burnett | Talent · Risk Assessment | 69 | Snelheid in beslissingen |
| The Dude | Talent · Psych Safety | 68 | Proactief richting kiezen |
| Frank the Pug | Talent · Signal Filter | 68 | Zichtbaarheid & kennisdeling |
| Jeffrey Beaumont | Talent · Hidden Patterns | 67 | Openheid & directe communicatie |
| The Narrator | Talent · Introspective | 66 | Actie naast reflectie versterken |
| Travis Bickle | Talent · Risk Detector | 65 | Nuance ontwikkelen & emotieregulatie |

### Worker (23)

| Persona | Badge | Score | Development prioriteit |
|---------|-------|-------|----------------------|
| Forrest Gump | Worker · Copywriter | 78 | Strategisch inzicht & contextbewustzijn |
| Winston Wolf | Worker · Incident Response | 78 | Kennisoverdracht & documentatie |
| Tony Stark | Worker · Senior Engineer | 77 | Delegeren & controle loslaten |
| Shuri | Worker · R&D / Innovation | 76 | Structuur & documentatie toevoegen |
| Lisbeth Salander | Worker · Security | 76 | Samenwerking & communicatie |
| Keanu Reeves | Worker · Reliable Executor | 75 | Zichtbaarheid & leiderschap |
| Mark Watney | Worker · Improvisation | 75 | Samenwerking & kennisdeling |
| Mike Ross | Worker · Research | 74 | Zelfvertrouwen & structuur |
| Q | Worker · Tooling / Infra | 74 | Zichtbaarheid & communicatie |
| Amélie Poulain | Worker · Support Specialist | 71 | Directe communicatie & zichtbaarheid |
| Ferris Bueller | Worker · GTM / Creative | 70 | Verantwoordelijkheid & transparantie |
| Man with No Name | Worker · Precision Executor | 73 | Kennisdeling & samenwerking |
| Amélie Poulain | Worker · Support Specialist | 71 | Directe communicatie & zichtbaarheid |
| Donnie Darko | Worker · SEO Research | 65 | Mentale stabiliteit & praktische toetsing |
| Vincent Vega | Worker · Task Executor | 67 | Proactiviteit & strategisch bewustzijn |
| Edward Scissorhands | Worker · Creative Design | 67 | Zelfvertrouwen & grenzen stellen |
| Mad Max | Worker · Incident Response | 68 | Emotionele verwerking & delegatie |
| Mike Lowrey | Worker · Action / Ops | 68 | Structuur & langetermijndenken |
| Agent J | Worker · Adaptive Ops | 67 | Structuur & discipline versterken |
| Jack Burton | Worker · Operations | 66 | Luisteren & realistische zelfinschatting |
| Lester Burnham | Worker · Creative | 64 | Structuur & focus voor consistent leveren |
| Tony Soprano | Worker · Operations Lead | 63 | Emotieregulatie & stabiliteit |
| Napoleon Dynamite | Worker · Niche Skills | 60 | Samenwerking & zelfvertrouwen |
| Alex DeLarge | Worker · Disruptive | 45 | Zwaar development traject vereist |

---

## 11. Van persona naar operationele agent — stappenplan

Dit is het exacte stappenplan dat Cursor volgt bij het aanmaken van een nieuwe agent.

### Stap 1 — Persona selecteren uit bibliotheek
- Selecteer persona op basis van gewenste rol en persoonlijkheidsfit
- Lees de drie 50-woorden secties (Persona, Kwaliteiten, Ontwikkeling)
- Sla `persona_source` op als referentie

### Stap 2 — Rol-template ophalen (sectie 5)
- Haal de standaard rol-template op voor de gewenste rol
- Vul de ontbrekende velden in: `tool_whitelist`, `output_format`, `guardrails`, `model_config`

### Stap 3 — System prompt samenstellen
Combineer de persona met de werkwijze-instructie. De system prompt heeft altijd deze vaste structuur:

```
## Identiteit
[Uit persona: wie ben je, persoonlijkheid, toon]

## Missie
[Uit goal: één heldere kernzin]

## Werkwijze
[Uit rol-template: stap-voor-stap werkproces]

## Kwaliteitseisen
[Uit guardrails.quality_thresholds: heldere normen]

## Escalatieregels
[Uit guardrails.escalation_rule: wanneer stop je]

## Wat je NIET doet
[Uit guardrails.scope_limitation + ontwikkeling: expliciete grenzen]
```

### Stap 4 — Development points aanmaken
- Vertaal de Ontwikkeling (50 woorden) naar 3 concrete initiële `development_points`
- Sla op in `development_points` tabel met `status = 'open'` en `impact = 'low'`

### Stap 5 — Knowledge base koppelen
- Koppel minimaal één relevante kennisbron
- Start de training workflow (scrape → chunk → embed → store in `agent_knowledge`)

### Stap 6 — Activeren
- Controleer of alle verplichte velden zijn ingevuld (zie sectie 4)
- Zet `is_active = true` pas als alle verplichte velden aanwezig zijn
- Log aanmaak als `system_event` met type `agent_created`

---

## 12. Cursor instructies

### 12.1 Wat Cursor WEL doet

- Agents aanmaken conform het datamodel in sectie 8
- `hired_agents` INSERT statements genereren met alle verplichte velden
- `development_points` aanmaken op basis van de Ontwikkeling-sectie van de persona
- `agent_knowledge` vullen via de training workflow
- `is_active` pas op `true` zetten als alle verplichte velden zijn ingevuld
- System events loggen bij elke statuswijziging

### 12.2 Wat Cursor NIET doet

- Agents aanmaken zonder `guardrails` of `output_format` — dit is een hard blocker
- `tool_whitelist` leeg laten — minimaal één tool is vereist
- `temperature` instellen boven 0.9 voor Talent-agents
- `is_suspended` en `is_active` allebei op `true` zetten
- Meerdere stappen tegelijk uitvoeren — bevestig na elke fase

### 12.3 Pre-flight checklist voor Cursor

Voer deze checklist uit vóór het aanmaken van een agent:

```sql
-- 1. Controleer of hired_agents tabel bestaat
SELECT COUNT(*) FROM hired_agents LIMIT 1;

-- 2. Controleer of agent_knowledge tabel bestaat met juiste embedding dimensie
SELECT * FROM agent_knowledge LIMIT 0;

-- 3. Controleer of development_points tabel bestaat
SELECT * FROM development_points LIMIT 0;

-- 4. Controleer of pgvector actief is
SELECT * FROM pg_extension WHERE extname = 'vector';
```

Als één van deze checks faalt: **stop en meld aan de gebruiker. Herstel eerst de ontbrekende component.**

### 12.4 Fasering bij batch-aanmaak

Bij het aanmaken van meerdere agents tegelijk:

1. **Fase 1:** Maak alle `hired_agents` records aan met `is_active = false`
2. **Fase 2:** Genereer development_points per agent
3. **Fase 3:** Koppel knowledge sources en start training
4. **Fase 4:** Activeer agents één voor één na succesvolle training
5. **Fase 5:** Rapporteer welke agents actief zijn en welke nog training nodig hebben

Bevestig na elke fase bij de gebruiker vóór je doorgaat.

---

## Versiehistorie

| Versie | Datum | Wijzigingen |
|--------|-------|-------------|
| 1.0 | 17 maart 2026 | Initieel document: platform-architectuur, universele anatomie, 49 personas ingedeeld, rol-templates, model-config, guardrails, database schema, Cursor instructies |

---

*Dit document is de authoritative bron voor agent-configuratie binnen Crew Intelligent. Bij conflicten tussen dit document en een implementatie prevaleert dit document totdat een nieuwe versie is goedgekeurd.*
