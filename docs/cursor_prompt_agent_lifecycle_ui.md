# Cursor Prompt — Agent Lifecycle UI
**Datum:** maart 2026 | **Versie:** v2.1 | **Ref:** Product Spec v1.1 sectie 2, 8 en 10 (fase 1–4)

---

## Context

De fundament-tabellen `hired_agents` en `agent_knowledge` bestaan al en werken.
Agent presets zijn beschikbaar via `GET /api/agents/presets` (4 presets: Max, Lisa, Emma, Donna).
Direct Chat is volledig geïmplementeerd (DC-1 t/m DC-12).

We bouwen nu de Agent Lifecycle UI: agents aanmaken via een formulier, bekijken en beheren.

**Belangrijk:** Alle `/api/agents` endpoints vereisen authenticatie (`require_super_admin`).
Elke API-aanroep vanuit de frontend moet een Supabase Bearer-token meesturen via de
`Authorization: Bearer <token>` header. Gebruik de bestaande `buildAuthHeaders()` uit `authz.js` (zoals AgentDirectChat en ClientsOverview). Dit geldt voor alle checks
en alle API-aanroepen in dit prompt.

---

## Pre-flight checks

Voer uit en rapporteer voor je begint. Alle checks draaien met auth-token.

**Stap 1 — Token ophalen:**
Log in via de UI (`http://localhost:3001/login`) en haal het token op via de browser console:
```javascript
const { data } = await supabase.auth.getSession();
console.log(data.session?.access_token);
```
Sla het token op als `TOKEN` voor de checks hieronder.

```bash
TOKEN="<access_token_uit_browser_console>"

# Check 1 — Presets endpoint werkt?
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8090/api/agents/presets | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Presets: {d[\"total\"]}')
[print(f'  - {p[\"display_name\"]}') for p in d['presets']]
"
# Verwacht: 4 presets (Max, Lisa, Emma, Donna)

# Check 2 — Agents endpoint werkt?
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8090/api/agents | python3 -c "
import sys, json
d = json.load(sys.stdin)
agents = d if isinstance(d, list) else d.get('agents', [])
print(f'Agents in DB: {len(agents)}')
for a in agents[:5]:
    print(f'  - {a.get(\"name\", \"?\")} ({a.get(\"role\", \"?\")})')
"
# Verwacht: lijst van agents (kan leeg zijn, maar geen 401/404)

# Check 3 — Schema hired_agents
psql $DATABASE_URL -c "\d hired_agents"
# Verwacht: kolommen incl. name, agent_id, role, goal, category,
#           is_active, system_prompt, tool_access_whitelist

# Check 4 — POST endpoint bestaat?
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  -X POST http://localhost:8090/api/agents \
  -H "Content-Type: application/json" -d '{}'
# Verwacht: 422 (validatiefout), niet 404

# Check 5 — VALID_TOOLS ophalen uit backend
grep -A 30 "VALID_TOOLS" app/routes/agents.py | head -35
# Verwacht: de definitieve lijst van toegestane tools
```

Rapporteer alle resultaten. Stop als een check faalt. Checks 1 en 2 zijn pas groen
als je een 200-response krijgt met de verwachte data — een 401 telt niet als groen.

---

## Kritieke implementatieregels

### 1. Auth op elke API-aanroep
Elke `fetch` of `axios` aanroep naar `/api/agents*` endpoints moet de header
`Authorization: Bearer <token>` meesturen. Gebruik de bestaande auth utility
in het project (zoek naar hoe andere componenten dit doen, bijv. de Direct Chat
implementatie). Implementeer geen eigen auth-logica — hergebruik wat er al is.

### 2. VALID_TOOLS synchroon houden
De tool checkboxes in `NewCrewMember.jsx` en de Profiel tab in `AgentDetail.jsx`
moeten **exact overeenkomen** met de `VALID_TOOLS` lijst in `app/routes/agents.py`.

- Lees `VALID_TOOLS` uit dat bestand voor je de checkboxes hardcodeert.
- Hardcode de lijst niet in de frontend — exporteer of documenteer hem als
  single source of truth. Als de backend-lijst wijzigt, moet de frontend
  dat reflecteren. Voeg een commentaarregel toe boven de checkboxes:
  `// Source of truth: app/routes/agents.py VALID_TOOLS — sync bij wijziging`

### 3. Error handling op 422
De backend geeft bij validatiefouten een `422 Unprocessable Entity` terug met
een `detail` veld (string of array van `{loc, msg, type}` objecten).
Implementeer dit als volgt:
- Als `detail` een array is: toon elke fout inline bij het betreffende veld
  (`loc` bevat de veldnaam).
- Als `detail` een string is: toon bovenaan het formulier als algemene foutmelding.
- Gebruik nooit een generieke "Er ging iets fout" melding als de backend
  specifieke informatie geeft.

---

## Backend — API uitbreiden (stap 1)

**Doel:** Zorg dat `GET /api/agents` en `PATCH /api/agents/{id}` de velden leveren die AL-1 t/m AL-4 nodig hebben.

**Bestand:** `app/routes/agents.py`

### Wijzigingen

1. **list_agents:** Voeg `category` en `is_active` toe aan de SELECT (nu ontbreken ze — AL-1 toont dan lege velden).
2. **AgentUpdate:** Voeg toe: `goal`, `category`, `is_active`.
3. **update_agent (PATCH):** Voeg `goal`, `category`, `is_active` toe aan de RETURNING-clause.

### Acceptatiecriteria
- [ ] `GET /api/agents` retourneert per agent `category` en `is_active`
- [ ] `PATCH /api/agents/{id}` accepteert `goal`, `category`, `is_active`
- [ ] PATCH response bevat de geüpdatete waarden

---

## FASE AL-1 — Agents overzicht pagina

**Doel:** Gebruiker ziet alle hired agents in een overzicht.

**Bestand:** `web_ui/frontend/src/AgentsOverview.jsx` (bestaat al — uitbreiden)

### Wat er moet staan:

- Tabel of kaartgrid met alle agents uit `GET /api/agents` (met auth-header)
- Per agent: naam, rol, categorie, is_active status badge (groen/grijs)
- Knoppen per agent: **Open chat** (→ `/agents/{id}?tab=chat`), **Bewerken** (→ `/agents/{id}`)
- Prominente **"+ Nieuwe agent"** knop rechtsboven → `/agents/new`
- Lege staat als er geen agents zijn: uitnodigende tekst + "Maak eerste agent aan" knop

### Acceptatiecriteria:
- [ ] Alle hired agents worden getoond (authenticated request)
- [ ] Status badge (actief/inactief) is zichtbaar
- [ ] "Open chat" link werkt naar Chat tab
- [ ] "+ Nieuwe agent" knop navigeert naar `/agents/new`
- [ ] Lege staat toont uitnodigende tekst

---

## FASE AL-2 — NewCrewMember formulier

**Doel:** Gebruiker kan een nieuwe agent aanmaken, optioneel vanuit een preset.

**Bestand:** `web_ui/frontend/src/NewCrewMember.jsx` (nieuw)

**Route:** `/agents/new`

### Stap 1 — Preset selectie (optioneel)

Laad presets via `GET /api/agents/presets` (met auth-header).
Toon als klikbare kaarten:
- Naam + beschrijving + categorie
- Klik op preset → vult het formulier voor in (alle velden inclusief system_prompt en tools)
- "Leeg beginnen" optie om preset over te slaan

### Stap 2 — Formulier velden

| Veld | Type | Koppelt aan | Verplicht |
|------|------|-------------|-----------|
| Naam | Text input | `agent_name` (POST body) | Ja |
| Rol | Text input (vrij) | `role` | Ja |
| Categorie | Dropdown | `category` | Ja |
| Doel binnen crew | Text input | `goal` | Ja |
| System Instructions | Textarea (groot, min 6 regels) | `system_prompt` | Ja |
| Tool Access | Multi-select checkboxes | `tool_whitelist` (POST body) | Nee |

**Categorieën dropdown:** Management, Content, Marketing, Operations, Technical, Support, Analytics, Custom

**Tool checkboxes:** Lees de exacte lijst uit `VALID_TOOLS` in `app/routes/agents.py`
(zie pre-flight check 5). Bouw op basis van de pre-flight output — niet op een hardcoded lijst uit het prompt.
Voeg commentaar toe: `// Source of truth: app/routes/agents.py VALID_TOOLS — sync bij wijziging`

**Preset invulling:** Presets hebben `suggested_tools`; de backend verwacht `tool_whitelist` in de POST-body.
Map bij voorinvullen: `suggested_tools` → `tool_whitelist` (niet tool_access_whitelist).

### Stap 3 — Opslaan

`POST /api/agents` met auth-header. Body (Hiring Hall spec): `{ agent_name, role, category, goal, system_prompt, tool_whitelist }`.

- Bij succes (201): redirect naar `/agents/{id}`
- Bij 422: toon inline fouten per veld (zie implementatieregel 3)
- Bij andere fout: toon algemene foutmelding met de status code

### Acceptatiecriteria:
- [ ] Presets worden geladen met auth
- [ ] Preset selectie vult alle velden voor in
- [ ] Alle verplichte velden gevalideerd voor submit
- [ ] POST naar `/api/agents` werkt met auth-header
- [ ] 422 fouten worden inline per veld getoond
- [ ] Na aanmaken: redirect naar agent detail pagina
- [ ] Agent verschijnt daarna in het overzicht

---

## FASE AL-3 — Agent bewerken

**Doel:** Gebruiker kan een bestaande agent updaten.

De agent detail pagina (`/agents/{id}`) heeft al een **Profiel tab** (DC-4).
Maak deze tab bewerkbaar:

- Velden: naam, doel, system instructions, tool whitelist, is_active
- **Eén** "Opslaan" knop → `PATCH /api/agents/{id}` met alle gewijzigde velden (met auth-header)
- **Annuleren** knop → reset naar originele waarden (geen API-aanroep)
- Verwijder bestaande losse save-handlers (saveName, saveSystemInstructions) — anders conflicterende opslaan-paden
- Tool checkboxes: gebruik gedeelde `agentConstants.js` (zelfde 18 tools als NewCrewMember)

**Bestand:** `web_ui/frontend/src/AgentDetail.jsx` — Profiel tab aanpassen

### Acceptatiecriteria:
- [ ] Profiel tab toont bewerkbare velden
- [ ] Tool checkboxes matchen exact met VALID_TOOLS
- [ ] PATCH endpoint werkt met auth-header
- [ ] 422 fouten worden getoond
- [ ] Annuleren reset velden zonder opslaan
- [ ] Wijzigingen zijn direct zichtbaar na opslaan

---

## FASE AL-4 — Agent activeren / deactiveren

**Doel:** CEO kan agent tijdelijk offline halen of heractiveren.

In de Profiel tab: toggle schakelaar voor `is_active`.

- Actief → inactief: bevestigingsmodal "Agent {naam} wordt gedeactiveerd. Lopende taken worden niet onderbroken."
- Inactief → actief: directe activatie zonder modal
- `PATCH /api/agents/{id}` met `{"is_active": false/true}` en auth-header
- Status badge in het overzicht update mee na wijziging

### Acceptatiecriteria:
- [ ] Toggle is zichtbaar in Profiel tab
- [ ] Deactiveren toont bevestigingsmodal
- [ ] PATCH met auth-header werkt
- [ ] Status badge in overzicht reflecteert de nieuwe waarde

---

## Implementatievolgorde

**Belangrijk:** Backend eerst. Als je AL-1 bouwt terwijl `category` en `is_active` nog niet in de GET-response zitten, debug je tegen lege velden.

Werk in deze volgorde. Na elke stap: laat zien wat gebouwd is, benoem de stap, wacht op bevestiging voor de volgende start.

1. **Backend** — `app/routes/agents.py`: `category` en `is_active` toevoegen aan `list_agents` SELECT; `goal`, `category`, `is_active` toevoegen aan `AgentUpdate` en PATCH RETURNING
2. **AL-1** — AgentsOverview
3. **AL-2** — NewCrewMember (grootste stap — herschrijven met preset selectie)
4. **AL-3** — Profiel tab bewerkbaar
5. **AL-4** — Activeer/deactiveer toggle

---

## Wat je NIET doet

- Geen wijzigingen aan `hired_agents` tabel structuur
- Geen wijzigingen aan bestaande chat of job flow logica
- Geen nieuwe backend tabellen
- Geen eigen auth-logica implementeren — hergebruik wat er al is
- Knowledge Base Sources (training via URL) valt onder Training Workflow —
  niet in dit formulier, alleen een link naar de Kennis tab

---

## Definitie van klaar

- [ ] Pre-flight checks groen (inclusief auth)
- [ ] Backend: list_agents en PATCH leveren category, is_active, goal
- [ ] Alle API-aanroepen gebruiken auth-header via bestaande auth utility
- [ ] Tool checkboxes matchen exact met `VALID_TOOLS` in `app/routes/agents.py`
- [ ] 422 fouten worden inline per veld getoond
- [ ] Gebruiker kan nieuwe agent aanmaken via UI (met of zonder preset)
- [ ] Agent verschijnt in overzicht
- [ ] Agent detail pagina toont bewerkbare Profiel tab
- [ ] Activeren/deactiveren werkt
- [ ] Geen bestaande functionaliteit gebroken
