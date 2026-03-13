# SPEC: HR Manager — Issue Detail Page
**Feature:** Development Point Detail View  
**Versie:** 1.0  
**Datum:** 13 maart 2026  
**Koppelt aan:** Product Spec v1.1 sectie 6 (HR Manager), `development_points` tabel  
**Route:** `/hr/issues/:pointId`  
**Component:** `IssueDetail.jsx`

---

## Wat je NIET doet

- Geen nieuwe tabellen aanmaken, alleen lezen uit bestaande schema's
- Geen wijzigingen aan de backend buiten de endpoints die in dit document staan
- Geen styling buiten de bestaande CSS-variabelen van het project aanraken
- Geen polling instellen, dit is een statische detailpagina (geen realtime vereist voor v1)
- Niet beginnen met bouwen zonder eerst de pre-flight checks uit te voeren

---

## Pre-flight checks (uitvoeren voor je begint)

Verifieer dat het volgende bestaat en werkt:

```
[ ] GET /api/hr/development-points         endpoint geeft data terug
[ ] development_points tabel aanwezig in DB (schema hieronder)
[ ] job_steps tabel aanwezig met retry_count, retry_reason kolommen
[ ] hired_agents tabel aanwezig
[ ] Bestaande HR-pagina (/hr of /dashboard) heeft een navigeerbare link
[ ] React Router v6 actief in het project
```

Rapporteer de uitkomst van elke check voor je verdergaat.

---

## Database schema (read-only referentie)

```sql
-- Bestaande tabel (niet aanpassen)
CREATE TABLE development_points (
  point_id        TEXT PRIMARY KEY,              -- bijv. DP-2026-03-047
  agent_id        TEXT REFERENCES hired_agents(agent_id),
  issue_description TEXT NOT NULL,
  root_cause      TEXT,
  evidence_example TEXT,
  frequency       INTEGER DEFAULT 1,
  impact          TEXT CHECK (impact IN ('low','medium','high')),
  source_url      TEXT,
  status          TEXT CHECK (status IN (
                    'OPEN','AWAITING_APPROVAL',
                    'IN_TRAINING','RESOLVED','DISMISSED'
                  )) DEFAULT 'OPEN',
  proposed_by     TEXT DEFAULT 'hr-manager',
  approved_by     TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  resolved_at     TIMESTAMPTZ
);
```

Extra velden die je via JOIN ophaalt:

```sql
-- hired_agents
agent_name, agent_version, role, model, temperature, top_p, max_tokens, workflow

-- job_steps (voor timeline)
step_id, job_id, agent_id, step_name, status, retry_count, retry_reason,
started_at, completed_at
```

---

## Nieuwe API endpoints (backend uitbreiden)

### GET `/api/hr/development-points/:pointId`

Geeft één development point terug, inclusief agent-info en timeline.

**Response schema:**

```json
{
  "point": {
    "point_id": "DP-2026-03-047",
    "issue_description": "Scan Retry Loop",
    "root_cause": "...",
    "evidence_example": "Job cdff169b-...",
    "frequency": 255,
    "impact": "low",
    "status": "OPEN",
    "created_at": "2026-02-11T09:00:00Z",
    "resolved_at": null
  },
  "agent": {
    "agent_id": "agent:senior-copywriter:max",
    "agent_name": "Max – Senior Copywriter",
    "agent_version": "v2.3.1",
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 4000,
    "workflow": "Blog Content Creation",
    "success_rate": 0.87
  },
  "timeline": [
    {
      "time": "14:01:02",
      "step": "Agent started",
      "status": "ok",
      "duration_s": null,
      "notes": "Workflow initialized"
    }
  ],
  "run_id": "cdff169b-b49b-4ec4-b61b-4099dcc071eb",
  "pattern": {
    "workflow": "Blog Content Creation",
    "trigger_condition": "700+ word input",
    "affected_version": "v2.3.1",
    "workflow_success_rate": 0.87,
    "failure_rate_condition": 0.13
  },
  "impact_stats": {
    "affected_jobs": 3,
    "total_retries": 255,
    "extra_cost_per_100": 2.10,
    "user_facing": false
  },
  "performance": {
    "success_rate": 0.92,
    "retry_rate": 0.06,
    "validation_failure_rate": 0.04,
    "avg_cost_per_run": 0.34
  },
  "evidence": [
    "cdff169b-b49b-4ec4-b61b-4099dcc071eb",
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  ],
  "feedback": {
    "text": "De validator is te streng. Maak subheadings verplicht in de prompt.",
    "author": "Operator",
    "created_at": "2026-03-13T14:15:00Z"
  }
}
```

### PATCH `/api/hr/development-points/:pointId`

Gebruikt voor alle statusmutaties vanuit de UI.

**Request body (afhankelijk van actie):**

```json
// Approve -> training
{ "action": "approve", "approved_by": "ceo" }

// False positive
{ "action": "dismiss", "reason": "false_positive" }

// Status handmatig zetten
{ "status": "RESOLVED" }
```

**Response:** Altijd `{ "success": true, "point_id": "...", "new_status": "..." }`

### POST `/api/hr/development-points/:pointId/reproduce`

Start een nieuwe job op basis van hetzelfde run_id. Geeft direct een `job_id` terug.

```json
// Response
{ "job_id": "...", "status": "RUNNING" }
```

---

## Frontend: component tree

```
IssueDetail.jsx                          ← pagina-root, data fetching
├── IssueHeader                          ← title, badges, breadcrumb, meta-stats
├── AgentInfoCard                        ← naam, versie, workflow, success rate
├── ModelSettingsCard                    ← model, temperature slider, top-p slider, max_tokens
├── IssueSummaryCard                     ← type, sub-type, status, impact, retries, jobs
├── RootCauseCard                        ← confidence ring, alert boxes (cause + fix)
├── DiagnosisSignalsCard                 ← signaallijst met gewichten (NIEUW)
├── FrequencyTrendCard                   ← 30-dag SVG chart (NIEUW)
├── InputCard                            ← task prompt, briefing, extra parameters
├── OutputCard                           ← output preview, validatieregels, alert
├── TimelineTable                        ← run_id + tijdlijn tabel
├── PatternAnalysisCard                  ← workflow, trigger, success/fail progress bars
├── CrossAgentCard                       ← tabel andere agents met zelfde patroon (NIEUW)
├── ImpactCard                           ← 4 metric tiles + user experience alert
├── CostProjectionCard                   ← projectie bars 1m/3m/12m (NIEUW)
├── FixRoadmapCard                       ← geprioriteerde actielijst (NIEUW)
├── PerformanceMetricsCard               ← 4 performance tiles met progress bars
├── ReproduceCard                        ← run_id display + reproduce knop
├── FeedbackCard                         ← feedback tekst + actieknoppen
└── EvidenceCard                         ← job ID lijst + versie-info
```

---

## Bestandsstructuur (aanmaken)

```
web_ui/frontend/src/
├── pages/
│   └── IssueDetail.jsx          ← hoofdpagina
├── components/hr/
│   ├── IssueHeader.jsx
│   ├── AgentInfoCard.jsx
│   ├── ModelSettingsCard.jsx
│   ├── IssueSummaryCard.jsx
│   ├── RootCauseCard.jsx
│   ├── DiagnosisSignalsCard.jsx
│   ├── FrequencyTrendCard.jsx
│   ├── InputCard.jsx
│   ├── OutputCard.jsx
│   ├── TimelineTable.jsx
│   ├── PatternAnalysisCard.jsx
│   ├── CrossAgentCard.jsx
│   ├── ImpactCard.jsx
│   ├── CostProjectionCard.jsx
│   ├── FixRoadmapCard.jsx
│   ├── PerformanceMetricsCard.jsx
│   ├── ReproduceCard.jsx
│   ├── FeedbackCard.jsx
│   └── EvidenceCard.jsx
```

Alle componenten leven in `/components/hr/` zodat ze later ook herbruikbaar zijn in het HR-overzicht.

---

## Routing

Voeg toe aan de bestaande React Router config:

```jsx
// App.jsx of router.jsx — toevoegen aan bestaande routes
import IssueDetail from './pages/IssueDetail';

<Route path="/hr/issues/:pointId" element={<IssueDetail />} />
```

Zorg ook dat vanuit de HR-overzichtspagina (development points tabel) elke rij navigeert naar `/hr/issues/:pointId`.

---

## IssueDetail.jsx — data fetching patroon

```jsx
import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { buildAuthHeaders } from '../authz';

export default function IssueDetail() {
  const { pointId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchIssue = async () => {
      try {
        const res = await fetch(
          `/api/hr/development-points/${pointId}`,
          { headers: buildAuthHeaders() }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchIssue();
  }, [pointId]);

  if (loading) return <LoadingState />;
  if (error)   return <ErrorState message={error} />;
  if (!data)   return <EmptyState />;

  return (
    <div className="issue-detail-page">
      <IssueHeader point={data.point} agent={data.agent} />

      <section className="section-group">
        <SectionLabel>Agent & configuratie</SectionLabel>
        <div className="grid-3">
          <AgentInfoCard agent={data.agent} />
          <ModelSettingsCard agent={data.agent} />
          <IssueSummaryCard point={data.point} />
        </div>
      </section>

      <section className="section-group">
        <SectionLabel>Diagnose</SectionLabel>
        <div className="grid-2">
          <RootCauseCard point={data.point} />
          <DiagnosisSignalsCard signals={data.signals} />
        </div>
      </section>

      <section className="section-group">
        <SectionLabel>Frequentietrend — afgelopen 30 dagen</SectionLabel>
        <FrequencyTrendCard trend={data.trend} />
      </section>

      <section className="section-group">
        <SectionLabel>Run evidence</SectionLabel>
        <div className="grid-2">
          <InputCard input={data.input} />
          <OutputCard output={data.output} />
        </div>
      </section>

      <section className="section-group">
        <SectionLabel>Execution timeline</SectionLabel>
        <TimelineTable timeline={data.timeline} runId={data.run_id} />
      </section>

      <section className="section-group">
        <SectionLabel>Patroon & correlatie</SectionLabel>
        <div className="grid-2">
          <PatternAnalysisCard pattern={data.pattern} />
          <CrossAgentCard correlations={data.cross_agent} />
        </div>
      </section>

      <section className="section-group">
        <SectionLabel>Impact & kosten</SectionLabel>
        <div className="grid-2">
          <ImpactCard stats={data.impact_stats} />
          <CostProjectionCard stats={data.impact_stats} trend={data.trend} />
        </div>
      </section>

      <section className="section-group">
        <SectionLabel>Aanbevolen fix roadmap</SectionLabel>
        <FixRoadmapCard />
      </section>

      <section className="section-group">
        <SectionLabel>Agent performance</SectionLabel>
        <PerformanceMetricsCard perf={data.performance} agent={data.agent} />
      </section>

      <section className="section-group">
        <SectionLabel>Acties</SectionLabel>
        <div className="grid-3">
          <ReproduceCard runId={data.run_id} pointId={pointId} />
          <FeedbackCard feedback={data.feedback} pointId={pointId} onAction={handleAction} />
          <EvidenceCard evidence={data.evidence} point={data.point} />
        </div>
      </section>
    </div>
  );
}
```

`handleAction` verwerkt alle PATCH-calls en refresht de data na succes.

---

## Component specs

### IssueHeader

Props: `{ point, agent }`

Toont:
- Breadcrumb: `HR Manager › Development Points › {point_id}`
- Issue-ID badge (monospace, subtiel)
- Status badge (OPEN / AWAITING_APPROVAL / IN_TRAINING / RESOLVED / DISMISSED)
- Impact badge (low / medium / high)
- Paginatitel (issue_description, groot, display font)
- Subtitel (korte samenvatting)
- Header stat-rij: Detected by, First seen, Last seen, Frequency (30d), Extra cost

Rechtsboven: knoppen `← Terug`, `Delen`, `Stuur naar CEO`

"Stuur naar CEO" roept aan: `PATCH /api/hr/development-points/:id` met `{ "action": "request_approval" }` en zet status op `AWAITING_APPROVAL`.

---

### AgentInfoCard

Props: `{ agent }`

Data-rijen: Naam, Versie, Skill tier, Workflow, Success rate (groen gekleurd)

---

### ModelSettingsCard

Props: `{ agent }`

Vaste rijen: Model (monospace), Max tokens (monospace)

Slider-visualisatie voor Temperature en Top-P:
- Label links (naam + tooltip icoon)
- Progress track in het midden (kleur: amber voor temp, blauw voor top-p)
- Thumbmarker op de juiste positie
- Waarde rechts (monospace)

Tooltip teksten:
- Temperature: "Bepaalt willekeur en creativiteit van het model"
- Top-P: "Beperkt tokenselectie tot de meest waarschijnlijke tokens"
- Max tokens: "Maximale outputlengte van de agent"

---

### IssueSummaryCard

Props: `{ point }`

Data-rijen: Type, Sub-type, Status (badge), Impact (badge), Retries per run, Affected jobs

---

### RootCauseCard

Props: `{ point }`

Bevat:
- SVG confidence ring (cirkel met dasharray, percentage in het midden)
- Alert box "Likely cause" (amber tint)
- Alert box "Suggested fix" met Option A en Option B (blue tint)

Confidence ring berekening:
```
circumference = 2 * π * r  →  bij r=26: ≈ 163.4
dashoffset = circumference * (1 - confidence)
```

---

### DiagnosisSignalsCard (NIEUW)

Props: `{ signals }` — array van signals

Elke signal:
```js
{
  icon: '🔁',
  name: 'Consistent retry pattern',
  description: 'All 3 retries failed with same reason',
  weight: 0.92    // 0–1
}
```

Per signal: icon + naam + beschrijving links, gewichtsbar + percentage rechts.
Gewichtsbar: breedte = weight * 100%.

Fallback als `signals` leeg is: lege state met tekst "Geen diagnosesignalen beschikbaar."

---

### FrequencyTrendCard (NIEUW)

Props: `{ trend }` — object met dagelijkse datapunten

```js
trend: {
  daily: [
    { date: '2026-02-11', failures: 6, successes: 44 },
    // ... 30 dagen
  ],
  total_failures: 255,
  peak_day: { date: '2026-03-07', count: 14 },
  daily_avg: 8.5,
  vs_prev_period_pct: 18   // +18% ten opzichte van vorige periode
}
```

De chart is een SVG-lijndiagram:
- Breedte 100%, hoogte 120px
- Twee lijnen: failures (amber) en successes (groen)
- Beide met gradient fill-area eronder
- Horizontale gridlijnen op 5, 10, 15
- Datummarkeringen onderaan (eerste dag, halverwege, vandaag)
- "Vandaag" markering als verticale gestippelde lijn

Onder de chart: 4 metric tiles (Total failures, Piekdag, Dagelijks gem., Trend).

Berekening SVG-coördinaten:
```js
const points = data.daily.map((d, i) => {
  const x = (i / (data.daily.length - 1)) * chartWidth;
  const y = chartHeight - (d.failures / maxValue) * chartHeight;
  return `${x},${y}`;
}).join(' ');
```

Fallback als `trend.daily` leeg of ontbreekt: lege state met tekst "Trenddata niet beschikbaar."

---

### InputCard

Props: `{ input }`

```js
input: {
  task_prompt: '...',
  briefing: { client: '...', audience: '...', goal: '...' },
  extra_params: { word_count: 800, tone: 'conversational', format: 'scan friendly' }
}
```

Toont:
- "Task prompt" label + code block
- "Input briefing" sectie met data-rijen
- "Extra parameters" sectie, waarbij `format: 'scan friendly'` rood/amber gemarkeerd is als conflicterend veld

---

### OutputCard

Props: `{ output }`

```js
output: {
  summary: '...',
  validation_rules: [
    { rule: 'H2 headings', passed: false },
    { rule: 'Bullet lists', passed: false },
    { rule: 'Scannable paragraphs', passed: false }
  ],
  problem_description: '...'
}
```

Toont:
- Status badge "Failed validation" rechtsboven
- "Output preview" code block (grijs, monospace)
- "Validatieregels — verwacht vs ontvangen" lijst (✗ rood bij failed)
- Alert box rood met probleembeschrijving

---

### TimelineTable

Props: `{ timeline, runId }`

Kolommen: Tijd | Stap | Status | Duur | Notities

Status badge per rij: `ok` → groene badge, `fail` → rode badge.

Run ID display: monospace block met kopieerknop.

---

### PatternAnalysisCard

Props: `{ pattern }`

Data-rijen + twee progress bars:
- Success rate workflow (groen)
- Failure rate bij trigger-conditie (amber)

---

### CrossAgentCard (NIEUW)

Props: `{ correlations }` — array van andere agents met zelfde patroon

```js
correlations: [
  {
    agent_name: 'Sophie – Content Creator',
    agent_id: 'agent:content-creator:sophie',
    version: 'v1.8.2',
    failures_30d: 91,
    impact: 'low',
    is_current: false
  }
]
```

Tabel: Agent | Versie | Failures (30d) | Impact

Eerste rij is altijd de huidige agent (gemarkeerd als "Dit issue").

Onderaan: alert box blauw als er 2+ correlaties zijn: "Cross-training kans gedetecteerd door HR Manager."

Fallback als leeg: "Geen andere agents met dit patroon gevonden."

---

### ImpactCard

Props: `{ stats }`

4 metric tiles: Affected jobs, Total retries, Extra cost / 100 runs, User impact.

Alert box amber: beschrijving van de gebruikerservaring.

---

### CostProjectionCard (NIEUW)

Props: `{ stats, trend }`

Projectie berekend op basis van `stats.extra_cost_per_100` en `trend.vs_prev_period_pct`.

```js
const monthlyFailures = trend.total_failures;
const growthRate = trend.vs_prev_period_pct / 100; // bijv. 0.18
const costPer100 = stats.extra_cost_per_100;

const thisMonth = (monthlyFailures / 100) * costPer100;
const nextMonth = thisMonth * (1 + growthRate);
const threeMonths = thisMonth + nextMonth + (nextMonth * (1 + growthRate));
const twelveMonths = /* iteratieve berekening */;
```

Horizontale progress bars per tijdspan (breedte relatief aan het maximum).

Alert box amber onderaan met gecombineerde cross-agent schatting (alle correlerende agents).

---

### FixRoadmapCard (NIEUW)

Props: geen (statisch op basis van root cause type — voor v1 hardcoded per issue type)

5 acties in volgorde:
1. Prompt updaten — "Quick win" badge (groen)
2. Cross-training andere agents — "Quick win" badge (groen)
3. Workflow-level format template — "Medium term" badge (amber)
4. Validatieregel threshold herzien — "Medium term" badge (amber)
5. A/B validatie na training — "Longer term" badge (rood)

Per actie: genummerd icoon (actie 1 actief/highlight), titel + badge, beschrijvingstekst.

In v2 kan dit dynamisch worden gegenereerd door de API op basis van `root_cause` type.

---

### PerformanceMetricsCard

Props: `{ perf, agent }`

4 tiles met progress bars: Success rate (groen), Retry rate (amber), Validation failures (rood), Avg cost per run (blauw).

---

### ReproduceCard

Props: `{ runId, pointId }`

Run ID display + grote reproduce-knop.

Bij klik: `POST /api/hr/development-points/:pointId/reproduce`

Loading state tijdens request: knoptekst verandert naar "Bezig..."
Bij succes: navigeer naar `/jobs/:job_id`

---

### FeedbackCard

Props: `{ feedback, pointId, onAction }`

Feedback quote (cursief, subtiel) met auteur en datum.

Actieknoppen (roepen `handleAction` aan):

| Knop | Actie | PATCH body |
|------|-------|-----------|
| Approve & train | Groen | `{ "action": "approve" }` |
| False positive | Rood | `{ "action": "dismiss", "reason": "false_positive" }` |
| Improve prompt | Amber | Navigeert naar agent-edit pagina |
| Adjust validator | Grijs | Modal (v2, voor nu: toast "Binnenkort beschikbaar") |

Na elke geslaagde actie: refresh de pagina-data en toon een toast-bericht.

---

### EvidenceCard

Props: `{ evidence, point }`

Lijst van job ID's als klikbare links naar `/jobs/:id`.

Data-rijen: "Patroon aanwezig since", "v2.2.0 affected?", "Gerelateerde lesson" (monospace).

Knop: "Alle evidence runs bekijken →" navigeert naar HR-overzicht gefilterd op dit point_id.

---

## Gedeelde UI-primitieven

Maak deze aan in `components/hr/shared/`:

```jsx
// Badge.jsx
// Props: variant ('open'|'ok'|'fail'|'low'|'medium'|'high'|'resolved'|'dismissed')
// + children

// ProgressBar.jsx
// Props: value (0-1), variant ('green'|'amber'|'red'|'blue')

// AlertBox.jsx
// Props: variant ('amber'|'green'|'red'|'blue'), title (optioneel), children

// DataRow.jsx
// Props: label, value, mono (bool), accentColor (optioneel)

// SectionLabel.jsx
// Props: children

// MetricTile.jsx
// Props: label, value, sub, trend, accentColor

// LoadingState.jsx
// Toont skeleton of spinner

// EmptyState.jsx
// Props: message

// ErrorState.jsx
// Props: message
```

---

## Styling — Wonderz Agentics design tokens

Bron: `web_ui/frontend/src/styles/wonderz.css`

Gebruik **uitsluitend** de variabelen hieronder. Geen nieuwe variabelen aanmaken, geen hardcoded hex-waarden buiten de uitzonderingen die hieronder expliciet zijn vermeld.

### Fonts

```css
font-family: var(--font-primary);   /* 'DM Sans', 'Segoe UI', sans-serif  — body, labels, knoppen */
font-family: var(--font-mono);      /* 'DM Mono', 'Fira Code', monospace  — run ID, versies, code blocks */
```

De referentie-HTML gebruikt Syne (display) en IBM Plex Mono. Vervang:
- Syne → `var(--font-primary)` met `font-weight: var(--font-bold)` voor titels
- IBM Plex Mono → `var(--font-mono)`

### Achtergronden & surfaces

```css
/* Paginaachtergrond */
background: var(--color-bg-page);          /* #F4F6FB */

/* Kaarten */
background: var(--color-bg-card);          /* #FFFFFF */
box-shadow: var(--shadow-card);

/* Subtiele achtergrond (code blocks, input fields, inner sections) */
background: var(--color-bg-subtle);        /* #F9FAFB */
background: var(--color-bg-input);         /* #F3F4F6 */
```

### Tekst

```css
color: var(--color-text-primary);          /* #111827  — hoofdtekst, waarden */
color: var(--color-text-secondary);        /* #374151  — labels, subtitels */
color: var(--color-text-muted);            /* #6B7280  — dimme labels, timestamps */
color: var(--color-text-placeholder);      /* #9CA3AF  — placeholders, lege states */
```

### Borders

```css
border: 1px solid var(--color-border);           /* #E5E7EB — standaard kaartrand */
border: 1px solid var(--color-border-subtle);    /* #F3F4F6 — interne scheidingslijnen */
```

### Statuskleur-mapping (semantisch → Wonderz token)

| Semantisch doel | CSS-variabele | Waarde |
|----------------|---------------|--------|
| Success / groen | `--color-status-success` | `#22D3A5` |
| Success achtergrond | `--color-status-success-bg` | `#D1FAF0` |
| Warning / amber | `--color-status-warning` | `#F59E0B` |
| Warning achtergrond | `--color-status-warning-bg` | `#FEF3C7` |
| Error / rood | `--color-status-error` | `#EF4444` |
| Error achtergrond | `--color-status-error-bg` | `#FEE2E2` |
| Info / blauw (running) | `--color-status-running` | `#3B82F6` |
| Info achtergrond | `--color-status-running-bg` | `#DBEAFE` |
| Brand primary / CTA | `--color-brand-primary` | `#2563EB` |
| Brand primary hover | `--color-brand-primary-hover` | `#1D4ED8` |
| Brand primary licht bg | `--color-brand-primary-light` | `#EFF6FF` |

### Badge-kleur-mapping (exacte stijlen per variant)

Gebruik deze klassen of inline stijlen consistent voor alle badges op de pagina:

```css
/* OPEN (pulserende dot) */
.badge-open {
  background: var(--color-status-warning-bg);
  color: #92400E;                              /* badge tekst warning — uit wonderz.css */
  border: 1px solid var(--color-status-warning);
}

/* OK / RESOLVED */
.badge-ok, .badge-resolved {
  background: var(--color-status-success-bg);
  color: #065F46;                              /* badge tekst success — uit wonderz.css */
  border: 1px solid var(--color-status-success);
}

/* FAIL / ERROR */
.badge-fail {
  background: var(--color-status-error-bg);
  color: #991B1B;                              /* badge tekst error — uit wonderz.css */
  border: 1px solid var(--color-status-error);
}

/* LOW impact */
.badge-low {
  background: var(--color-status-running-bg);
  color: #1E40AF;                              /* badge tekst running — uit wonderz.css */
  border: 1px solid var(--color-status-running);
}

/* MEDIUM impact */
.badge-medium {
  background: var(--color-status-warning-bg);
  color: #92400E;
  border: 1px solid var(--color-status-warning);
}

/* HIGH impact */
.badge-high {
  background: var(--color-status-error-bg);
  color: #991B1B;
  border: 1px solid var(--color-status-error);
}

/* AWAITING_APPROVAL / IN_TRAINING */
.badge-pending {
  background: var(--color-brand-primary-light);
  color: var(--color-brand-primary);
  border: 1px solid var(--color-brand-primary);
}

/* DISMISSED */
.badge-dismissed {
  background: var(--color-bg-subtle);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
}
```

### Alert boxes (semantische achtergronden)

```css
/* Warning / amber */
.alert-warning {
  background: var(--color-status-warning-bg);
  border: 1px solid var(--color-status-warning);
  color: #92400E;
}

/* Success / groen */
.alert-success {
  background: var(--color-status-success-bg);
  border: 1px solid var(--color-status-success);
  color: #065F46;
}

/* Error / rood */
.alert-error {
  background: var(--color-status-error-bg);
  border: 1px solid var(--color-status-error);
  color: #991B1B;
}

/* Info / blauw */
.alert-info {
  background: var(--color-brand-primary-light);
  border: 1px solid var(--color-brand-primary);
  color: var(--color-brand-primary);
}
```

### Progress bars

```css
/* Track (altijd) */
.progress-track {
  background: var(--color-bg-input);    /* #F3F4F6 */
  border-radius: var(--radius-full);
  height: 6px;
}

/* Fill-varianten */
.progress-fill-success  { background: var(--color-status-success); }
.progress-fill-warning  { background: var(--color-status-warning); }
.progress-fill-error    { background: var(--color-status-error); }
.progress-fill-primary  { background: var(--color-brand-primary); }
```

### Knoppen

```css
/* Primaire actie (Approve, Reproduce, Stuur naar CEO) */
.btn-primary {
  background: var(--color-brand-primary);
  color: #FFFFFF;
  border: none;
  border-radius: var(--radius-sm);
}
.btn-primary:hover { background: var(--color-brand-primary-hover); }

/* Succes actie (Approve & train) */
.btn-success {
  background: var(--color-status-success-bg);
  color: #065F46;
  border: 1px solid var(--color-status-success);
  border-radius: var(--radius-sm);
}

/* Danger actie (False positive) */
.btn-danger {
  background: var(--color-status-error-bg);
  color: #991B1B;
  border: 1px solid var(--color-status-error);
  border-radius: var(--radius-sm);
}

/* Warning actie (Improve prompt) */
.btn-warning {
  background: var(--color-status-warning-bg);
  color: #92400E;
  border: 1px solid var(--color-status-warning);
  border-radius: var(--radius-sm);
}

/* Ghost / secundair */
.btn-ghost {
  background: var(--color-bg-card);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
.btn-ghost:hover { background: var(--color-bg-subtle); }
```

### Radius & spacing

```css
/* Kaarten */
border-radius: var(--radius-md);    /* 10px */

/* Knoppen, badges, kleine elementen */
border-radius: var(--radius-sm);    /* 6px */

/* Pills / full-round badges */
border-radius: var(--radius-full);  /* 9999px */

/* Card padding */
padding: var(--space-5);            /* 20px */

/* Sectie-gap */
gap: var(--space-4);                /* 16px */
margin-bottom: var(--space-3);      /* 12px */
```

### Impact-kleuren (HRDashboard hardcoded, overnemen zoals ze zijn)

Voor de `impact` badges en `FixRoadmapCard` badges gebruik je deze hardcoded waarden (consistent met de bestaande HRDashboard):

```css
/* Impact high */
color: #E74C3C;
background: #FDEDEC;

/* Impact medium */
color: #E67E22;
background: #FEF5E7;

/* Impact low / stable */
color: #95A5A6;
background: var(--color-bg-subtle);
```

### Chart-kleuren (consistent met ClientDashboard)

```css
/* SVG frequentiechart — lijn + fill */
stroke: var(--color-status-warning);          /* failures lijn — amber */
stroke: var(--color-status-success);          /* successes lijn — groen */
fill: var(--color-status-warning-bg);         /* failures fill-area */
fill: var(--color-status-success-bg);         /* successes fill-area */

/* Gridlijnen */
stroke: var(--color-border);                  /* #E5E7EB */

/* Cost projection bars */
fill: var(--color-status-warning);            /* dichtbij */
fill: var(--color-status-error);              /* ver weg / worst case */
```

### Shadows

```css
/* Kaarten */
box-shadow: var(--shadow-card);      /* 0 16px 32px rgba(15,23,42,0.08) */

/* Hover-staat kaarten */
box-shadow: var(--shadow-hover);

/* Modals (toekomstig) */
box-shadow: var(--shadow-modal);
```

### Grid utility classes

Voeg toe aan `wonderz.css` als ze nog niet bestaan:

```css
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-4); }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-3); }
.section-group { margin-bottom: var(--space-3); }

@media (max-width: 900px) {
  .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
}
```

### Wat je niet doet met styling

- Geen dark-theme kleuren gebruiken (de `#0d0f14` / `#151820` palette van AgentsPage is een uitzondering voor die pagina, niet de norm)
- Geen Syne, IBM Plex of andere fonts importeren
- Geen box-shadows zelf schrijven, alleen `var(--shadow-*)` gebruiken
- Geen `rgba()` of `opacity` trucs voor statuskleuren, gebruik de `*-bg` variabelen

---

## Empty states

Elke kaart moet een lege staat afhandelen:

```jsx
if (!data || data.length === 0) {
  return (
    <div className="card empty-state">
      <p>Geen data beschikbaar.</p>
    </div>
  );
}
```

---

## Toast-berichten

Gebruik de bestaande toast/notification implementatie van het project.

| Actie | Toast tekst |
|-------|------------|
| Approve gelukt | "Development point goedgekeurd. Training wordt gestart." |
| Dismiss gelukt | "Development point gesloten als false positive." |
| Reproduce gestart | "Run gestart. Navigeren naar job..." |
| Copy run ID | "Run ID gekopieerd." |
| Fout bij API-call | "Actie mislukt. Probeer opnieuw." |

---

## Acceptatiecriteria

Na implementatie moeten de volgende checks slagen:

```
[ ] /hr/issues/:pointId laadt correct voor een bestaand point_id
[ ] /hr/issues/onbekend toont een foutpagina (niet een crash)
[ ] Alle 14+ secties zijn zichtbaar en gevuld met data van de API
[ ] Frequency trend chart rendert zonder fouten (ook als daily leeg is)
[ ] Cross-agent correlaties tonen correct (of lege staat bij geen correlaties)
[ ] "Approve & train" zet status op AWAITING_APPROVAL in de DB
[ ] "False positive" zet status op DISMISSED in de DB
[ ] "Reproduce Run" navigeert naar /jobs/:job_id na succes
[ ] "Stuur naar CEO" zet status op AWAITING_APPROVAL
[ ] Run ID kopieerknop werkt
[ ] Layout is responsive op 1200px, 900px en 600px
[ ] Geen console errors in productie build
[ ] buildAuthHeaders() gebruikt op alle fetch-calls
```

---

## Fasering (voer in volgorde uit)

**Fase 1 — Backend (30 min)**
- `GET /api/hr/development-points/:pointId` endpoint
- `PATCH /api/hr/development-points/:pointId` endpoint
- `POST /api/hr/development-points/:pointId/reproduce` endpoint
- Verifieer alle drie met directe curl/test voor je doorgaat

**Fase 2 — Basis pagina-structuur (20 min)**
- `IssueDetail.jsx` aanmaken met data fetching
- Route toevoegen
- Loading, error en empty state
- Gedeelde primitieven aanmaken

**Fase 3 — Configuratiesectie (20 min)**
- `IssueHeader`, `AgentInfoCard`, `ModelSettingsCard`, `IssueSummaryCard`

**Fase 4 — Diagnosesectie (30 min)**
- `RootCauseCard` (confidence ring vereist nauwkeurige SVG-berekening)
- `DiagnosisSignalsCard`

**Fase 5 — Trendsectie (30 min)**
- `FrequencyTrendCard` (SVG-chart, coördinatenberekening, 4 metric tiles)

**Fase 6 — Evidence sectie (20 min)**
- `InputCard`, `OutputCard`, `TimelineTable`

**Fase 7 — Patroon & correlatie (20 min)**
- `PatternAnalysisCard`, `CrossAgentCard`

**Fase 8 — Impact & kosten (20 min)**
- `ImpactCard`, `CostProjectionCard`

**Fase 9 — Roadmap & performance (15 min)**
- `FixRoadmapCard`, `PerformanceMetricsCard`

**Fase 10 — Acties (20 min)**
- `ReproduceCard`, `FeedbackCard`, `EvidenceCard`
- Alle PATCH-calls aansluiten
- Toasts koppelen

**Fase 11 — Review & acceptatiecriteria (15 min)**
- Alle acceptatiecriteria doorlopen
- Responsive layout verifiëren
- Console errors opruimen

---



---

*Spec gegenereerd: 13 maart 2026 | Koppelt aan: Product Spec v1.1 sectie 6 | Volgende spec: HR Overview page*
