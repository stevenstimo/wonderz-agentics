# 260316 — CURSOR: Live Document Viewer (Claude-style artifact panel)

## Doel

Het rechter paneel van de JobDetail view transformeren naar een **live document viewer**, exact zoals het artifact-paneel in Claude.ai werkt:

- Links: de agent-chat (bestaande IntakeChat / PlanViewer / LiveTracker / ReviewDiff)
- Rechts: het document dat live opgebouwd wordt, rendered, scrollbaar, met toolbar
- Per status-change toont het rechter paneel andere content
- Updates via de bestaande polling loop (geen WebSocket nodig)

Dit is een **frontend-only refactor** + kleine backend-aanvulling voor tussentijdse content-opslag. Geen nieuwe tabellen. Geen breaking changes op bestaande flows.

---

## Pre-flight checks (STOP als één hiervan faalt)

1. [ ] Bevestig dat `JobDetail` component bestaat en de job pollt via `useEffect` + interval
2. [ ] Bevestig dat `job.proposed_data` en `job.artifact` beschikbaar zijn in de job-response van `GET /api/jobs/{id}`
3. [ ] Bevestig dat `job.status` de volgende waarden kan hebben: `INTAKE_CLARIFICATION`, `PLAN_PROPOSED`, `RUNNING`, `JOB_READY`, `COMPLETED`
4. [ ] Bevestig dat `copy_agent.py` het gegenereerde artifact wegschrijft naar de database (kolom `artifact` of `proposed_data` op de job)
5. [ ] Bevestig huidige layout van JobDetail: is het al een split-view (chat links, panel rechts)?

Rapporteer pre-flight resultaat voor je verder gaat.

---

## Fasering

### Fase 1 — Backend: tussentijdse content beschikbaar maken

**Doel:** Zorg dat de job-response altijd een `document_preview` veld bevat, per fase de juiste content.

**Bestanden:** `app/routes/jobs.py`

**Wijziging:** Voeg in de `GET /api/jobs/{id}` response een `document_preview` veld toe dat wordt samengesteld op basis van `status`:

```python
def build_document_preview(job: dict) -> dict:
    status = job.get("status")
    context = job.get("context") or {}
    if isinstance(context, str):
        import json
        try:
            context = json.loads(context)
        except Exception:
            context = {}

    proposed_data = job.get("proposed_data") or {}
    if isinstance(proposed_data, str):
        import json
        try:
            proposed_data = json.loads(proposed_data)
        except Exception:
            proposed_data = {}

    artifact = job.get("artifact") or ""

    if status == "INTAKE_CLARIFICATION":
        return {
            "type": "brief",
            "title": "Client Brief",
            "content": context.get("client_brief") or context.get("description") or job.get("description") or "",
            "subtitle": "Wordt aangevuld tijdens intake"
        }
    elif status == "PLAN_PROPOSED":
        steps = proposed_data.get("steps") or []
        return {
            "type": "plan",
            "title": "Voorgesteld Plan",
            "steps": steps,
            "subtitle": f"{len(steps)} stappen"
        }
    elif status == "RUNNING":
        partial = proposed_data.get("partial_content") or proposed_data.get("draft") or artifact or ""
        return {
            "type": "draft",
            "title": "Bezig met genereren...",
            "content": partial,
            "subtitle": "Live preview"
        }
    elif status in ("JOB_READY", "COMPLETED"):
        content = artifact or proposed_data.get("content") or proposed_data.get("text") or ""
        return {
            "type": "final",
            "title": job.get("description") or "Document",
            "content": content,
            "subtitle": "Klaar voor review" if status == "JOB_READY" else "Goedgekeurd"
        }
    else:
        return {
            "type": "empty",
            "title": "Document",
            "content": "",
            "subtitle": ""
        }
```

Voeg `document_preview: build_document_preview(job_dict)` toe aan de job-response payload van `GET /api/jobs/{id}`.

**Acceptatiecriteria Fase 1:**
- [ ] `GET /api/jobs/{id}` geeft altijd een `document_preview` object terug
- [ ] Per status bevat het de juiste `type`, `title`, `content` / `steps`
- [ ] Bestaande job-endpoints zijn onveranderd

Stop na Fase 1 en rapporteer.

---

### Fase 2 — Frontend: DocumentViewer component

**Doel:** Nieuw component `DocumentViewer.jsx` dat de `document_preview` rendert, identiek in gevoel aan het Claude artifact-paneel.

**Bestand:** `src/components/DocumentViewer.jsx` (nieuw)

**Visuele vereisten:**
- Witte achtergrond, lichte border-left scheiding van de chat
- Sticky header met: document-icon, titel, subtitle, en een toolbar rechts (Copy-knop, optioneel Download-knop)
- Content area: scrollbaar, lijn-hoogte 1.7, goede typografie
- Per `type` een andere renderer:
  - `brief`: plain tekst, licht grijze achtergrond, zoals een notitieblok
  - `plan`: genummerde stappen als kaarten, elke stap heeft een nummer-badge en tekst
  - `draft`: tekst met een subtiele "writing..." indicator bovenaan als content leeg is, anders de partial tekst. Cursor-knipperanimatie als het RUNNING is.
  - `final`: volledig gerenderde tekst, markdown-achtig (paragrafen, vetgedrukt), met approve/feedback knoppen **in het document paneel zelf** als status `JOB_READY` is
  - `empty`: lege state met een icoon en "Wacht op agent..."

**Toolbar gedrag:**
- Copy: kopieert de huidige content naar clipboard, knop verandert kort naar "Gekopieerd ✓"
- Download: download content als `.txt` bestand met de job-titel als bestandsnaam (alleen zichtbaar als `type === 'final'`)

**Animatie:** Bij status-change (type wijzigt) een korte fade-in van de nieuwe content (opacity 0 → 1, 300ms).

**Markdown rendering:**
Installeer `react-markdown` voor de content rendering:
```bash
npm install react-markdown
```
Gebruik het in DocumentViewer voor alle content-types die tekst renderen (`brief`, `draft`, `final`):
```jsx
import ReactMarkdown from 'react-markdown'
// ...
<ReactMarkdown>{content}</ReactMarkdown>
```
Geen extra plugins nodig. Standaard react-markdown ondersteunt headers, bold, italic, lists en paragrafen — dat is voldoende.

**Wat je NIET doet:**
- Geen andere markdown libraries installeren (geen remark-plugins, geen rehype, geen syntax highlighter)
- Geen nieuwe state management. Component is puur controlled: ontvangt `documentPreview` als prop.
- Geen polling in dit component. Polling blijft in de parent.

**Acceptatiecriteria Fase 2:**
- [ ] Component rendert correct voor alle 5 types
- [ ] Toolbar Copy werkt
- [ ] Fade-animatie bij type-change
- [ ] Geen console errors
- [ ] Approve/Feedback knoppen in final-view roepen de bestaande handlers aan (als prop doorgegeven)

Stop na Fase 2 en rapporteer.

---

### Fase 3 — Frontend: JobDetail layout refactor

**Doel:** De bestaande JobDetail view integreren met DocumentViewer. De layout wordt een echte split: chat links, document rechts.

**Bestand:** `src/pages/JobDetail.jsx` (of vergelijkbaar bestandsnaam)

**Wijzigingen:**

1. Voeg `documentPreview` toe aan de job-state: `job.document_preview` (al aanwezig na Fase 1)
2. Verwijder het huidige rechter paneel (Output panel dat de agent-vraag herhaalt)
3. Vervang met `<DocumentViewer documentPreview={job.document_preview} ... />`
4. Geef de bestaande `handleApprove` en `handleFeedback` functies als props mee aan DocumentViewer
5. Layout: `display: grid; grid-template-columns: 1fr 1fr;` op het wrapper element. Chat-kolom: `overflow-y: auto`. Viewer-kolom: `overflow-y: auto`, `border-left: 1px solid #e5e7eb`.
6. Op mobiel (< 768px): kolommen worden rijen, viewer bovenaan, chat onderaan.

**Wat je NIET doet:**
- Geen bestaande polling logica aanraken
- Geen bestaande chat-componenten (IntakeChat, PlanViewer, etc.) aanpassen
- Geen nieuwe routes aanmaken

**Acceptatiecriteria Fase 3:**
- [ ] Split-layout zichtbaar in browser
- [ ] DocumentViewer update live als job-status verandert (via bestaande polling)
- [ ] Approve en Feedback werken nog steeds correct
- [ ] Geen regressie op bestaande flows

Stop na Fase 3 en rapporteer.

---

### Fase 4 — Polish: streaming-effect bij RUNNING

**Doel:** Als de status `RUNNING` is en `partial_content` leeg is (agent is nog bezig), toon een subtiele "typewriter" indicator in het document paneel, zodat het voelt alsof er live getypt wordt.

**Alleen in `DocumentViewer.jsx`:**

- Als `type === 'draft'` en `content` leeg is: toon een animerende cursor (`|`) die knippert, plus de tekst "Agent is aan het schrijven..."
- Als `content` wel gevuld is: render de partial tekst normaal, plus de knipperende cursor aan het einde

**CSS:**
```css
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.cursor-blink {
  animation: blink 1s step-end infinite;
  font-weight: bold;
  color: #6366f1;
}
```

**Acceptatiecriteria Fase 4:**
- [ ] Knipperende cursor zichtbaar bij RUNNING status
- [ ] Geen knipperende cursor bij andere statussen
- [ ] Geen performance impact (pure CSS animatie)

---

## Wat je NOOIT doet (over alle fases)

- Geen WebSocket implementeren (dat is een aparte, latere taak)
- Geen nieuwe npm packages installeren zonder expliciete goedkeuring
- Geen wijzigingen aan de database schema
- Geen aanpassingen aan bestaande agent-bestanden (`copy_agent.py`, `reviewer_agent.py`, etc.)
- Geen TypeScript migratie
- Niet de bestaande `ReviewDiff` component verwijderen (DocumentViewer vervangt alleen het huidige Output-paneel, niet ReviewDiff)
- Geen `console.log` statements achterlaten

---

## Definitie van klaar

- [ ] Fase 1 t/m 4 succesvol afgerond
- [ ] Pre-flight checks allemaal groen
- [ ] Volledige end-to-end flow getest: INTAKE → PLAN → RUNNING → JOB_READY → COMPLETED
- [ ] Rechter paneel toont per fase de juiste content
- [ ] Approve en Feedback werken vanuit het document paneel
- [ ] Geen regressies op bestaande functionaliteit

---

## Deployment na afronding

```bash
cd ~/wonderz-agentics && git add -A && git commit -m "feat: live document viewer (Claude-style artifact panel)" && git push && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build
```
