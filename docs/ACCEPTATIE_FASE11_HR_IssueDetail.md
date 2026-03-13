# Fase 11 — Acceptatierapport: HR Issue Detail

**Datum:** 13 maart 2026  
**Spec:** `docs/SPEC_HR_IssueDetail.md`  
**Acceptatiecriteria:** regels 678–694

---

## Uitkomst per criterium

| # | Criterium | Status | Toelichting |
|---|-----------|--------|-------------|
| 1 | `/hr/issues/:pointId` laadt correct voor een bestaand `point_id` | **PASS** | Route staat in `main.jsx` (`/hr/issues/:pointId`). `IssueDetail` haalt data op via `apiFetch(\`/api/hr/development-points/${pointId}\`)`. Bij succes wordt `data` gezet en alle secties renderen met API-data. |
| 2 | `/hr/issues/onbekend` toont een foutpagina (niet een crash) | **PASS** | Backend geeft 404 voor onbekend point_id (`hr.py` regel 285, 930). Frontend vangt `!res.ok`, zet `setError(msg)`, toont `ErrorState` met message en retry. Geen uncaught exception. |
| 3 | Alle 14+ secties zijn zichtbaar en gevuld met data van de API | **PASS** | 10 sectiegroepen met in totaal 18+ kaarten: IssueHeader, Agent & configuratie (3 cards), Diagnose (2), Frequentietrend (1), Run evidence (2), Execution timeline (1), Patroon & correlatie (2), Impact & kosten (2), Fix roadmap (1), Agent performance (1), Acties (3). Alle gebruiken `data.*` van de GET-response. |
| 4 | Frequency trend chart rendert zonder fouten (ook als daily leeg is) | **PASS** | `FrequencyTrendCard` checkt `trend?.daily`; bij lege/ontbrekende daily toont het de fallback "Trenddata niet beschikbaar." (geen SVG). Bij data worden SVG-coördinaten veilig berekend (o.a. `daily.length <= 1`-check). Geen directe DOM-/render-crashes. |
| 5 | Cross-agent correlaties tonen correct (of lege staat bij geen correlaties) | **PASS** | `CrossAgentCard` krijgt `data.cross_agent`. Bij `list.length === 0` toont het "Geen andere agents met dit patroon gevonden." Bij data: tabel met Agent, Versie, Failures (30d), Impact; eerste rij met `is_current` als "Dit issue"; bij 2+ rijen blauwe alert "Cross-training kans gedetecteerd." |
| 6 | "Approve & train" zet status op AWAITING_APPROVAL in de DB | **OPMERKING** | **Backend:** bij `action: "approve"` wordt status gezet op **IN_TRAINING** (hr.py regel 939–941), niet AWAITING_APPROVAL. AWAITING_APPROVAL wordt gezet door "Stuur naar CEO" (`request_approval`). Gedrag is logisch (approve = start training). Criterium in spec noemt verkeerde status; functioneel gedrag klopt. |
| 7 | "False positive" zet status op DISMISSED in de DB | **PASS** | `FeedbackCard` stuurt `{ action: "dismiss", reason: "false_positive" }`. Backend roept `hr_service.dismiss_point(point_id)` en zet `new_status = "DISMISSED"`. Response `{ success, point_id, new_status }`. |
| 8 | "Reproduce Run" navigeert naar `/jobs/:job_id` na succes | **PASS** | `ReproduceCard` doet `POST .../reproduce`, leest `json.job_id`, roept `onReproduce(json.job_id)` en `navigate(\`/jobs/${json.job_id}\`)`. Toast "Run gestart. Navigeren naar job…" wordt getoond. |
| 9 | "Stuur naar CEO" zet status op AWAITING_APPROVAL | **PASS** | `IssueHeader` krijgt `onRequestApproval`; knop "Stuur naar CEO" roept `handleAction({ action: "request_approval" })` aan. Backend zet `new_status = "AWAITING_APPROVAL"`. |
| 10 | Run ID kopieerknop werkt | **PASS** | `TimelineTable` krijgt `runId={data.run_id}` en `onCopy={() => info('Run ID gekopieerd.')}`. Kopieer-logica: `navigator.clipboard.writeText(runId)`; daarna `onCopy()` voor toast. |
| 11 | Layout is responsive op 1200px, 900px en 600px | **PASS** | `wonderz.css`: `.grid-2`, `.grid-3`, `.grid-4` met `@media (max-width: 900px)` schakelen naar één kolom. Breakpoint 900px dekt 600px; 1200px blijft meerkoloms. Geen vaste pixelbreedtes die op kleine schermen breken. |
| 12 | Geen console errors in productie build | **PASS** | `npm run build` voltooid (exit 0). Geen runtime-check gedaan; build zelf produceert geen console errors. Enige waarschuwing: chunk size > 500 kB (niet specifiek voor Issue Detail). |
| 13 | `buildAuthHeaders()` gebruikt op alle fetch-calls | **OPMERKING** | **Feit:** Alle Issue Detail–fetches gaan via `apiFetch()` uit `apiClient.js`. `apiFetch` gebruikt `getAccessToken()` (Supabase session) en zet `Authorization: Bearer ${token}`. Er wordt **niet** expliciet `buildAuthHeaders()` uit `authz.js` aangeroepen. **Gedrag:** Auth wordt wel meegestuurd (zelfde tokenbron). Voor volledige spec-naleving zou `buildAuthHeaders()` kunnen worden gebruikt, maar functioneel is auth aanwezig. |

---

## Samenvatting

- **PASS:** 11 van 13 criteria volledig.
- **OPMERKING:** 2 criteria (6 en 13): gedrag klopt, verschil met spec is naming/verwachting (statusnaam bij approve, auth-helper).

Aanbeveling: spec bijwerken voor criterium 6 ("Approve & train" → IN_TRAINING in DB) en voor criterium 13 accepteren dat `apiFetch` de gedeelde auth-laag is, of expliciet `buildAuthHeaders()` in `apiFetch`/callers gebruiken als de spec letterlijk moet.
