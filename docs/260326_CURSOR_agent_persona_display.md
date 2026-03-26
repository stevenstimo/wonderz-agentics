# 260326_CURSOR_agent_persona_display

## Verplichte git-regels

- Nooit `git restore`, `git checkout --force`, `git reset` of `git clean` uitvoeren
- Bij elke git-operatie eerst `git status` rapporteren en wachten op bevestiging
- Alleen specifieke bestanden stagen, nooit `git add -A`

---

## Context

Wonderz-Agentics, React/Vite frontend + FastAPI backend.
Newbies hebben `persona`, `qualities` en `development` velden in de `newbies` tabel.
Agents hebben dezelfde `agent_id` als `newbie_id` in de newbies tabel.
Op de AgentDetail pagina zijn deze velden nu niet zichtbaar.
Op de NewbieDetail pagina zijn ze wel zichtbaar.

Doel: persona, kwaliteiten en ontwikkelpunten tonen op zowel NewbieDetail als AgentDetail.

---

## Pre-flight

```bash
# 1. Bekijk hoe NewbieDetail de velden toont
grep -n "persona\|qualities\|development\|Kwaliteiten\|Ontwikkelpunten" \
  web_ui/frontend/src/NewbieDetail.jsx | head -20

# 2. Bekijk de huidige AgentDetail structuur
grep -n "persona\|qualities\|development\|system_prompt\|Profiel" \
  web_ui/frontend/src/AgentDetail.jsx | head -20

# 3. Check of het backend agent endpoint al persona data meegeeft
grep -rn "persona\|qualities\|development" app/routes/agents.py | head -20
```

Rapporteer de output. Ga direct door.

---

## Wat je bouwt

### Stap 1 — Backend: persona data toevoegen aan agent response

Zoek het `GET /api/agents/{agent_id}` endpoint in `app/routes/agents.py`.
Voeg een JOIN toe met de `newbies` tabel om `persona`, `qualities` en `development` mee te geven:

```sql
SELECT 
  h.*,
  n.persona,
  n.qualities,
  n.development
FROM hired_agents h
LEFT JOIN newbies n ON n.newbie_id = h.agent_id
WHERE h.agent_id = $1
```

Voeg ook toe aan de lijst-endpoint `GET /api/agents` als dat nog niet aanwezig is.

### Stap 2 — Frontend: toon de velden op AgentDetail

Zoek in `AgentDetail.jsx` de plek waar het Profiel tab wordt gerenderd.
Voeg drie secties toe onder of naast de bestaande profiel-informatie, identiek aan de stijl van NewbieDetail:

```jsx
{agent.persona && (
  <div className="persona-section">
    <h3>Persona</h3>
    <p>{agent.persona}</p>
  </div>
)}

{agent.qualities && (
  <div className="qualities-section">
    <h3>Kwaliteiten</h3>
    <p>{agent.qualities}</p>
  </div>
)}

{agent.development && (
  <div className="development-section">
    <h3>Ontwikkelpunten</h3>
    <p>{agent.development}</p>
  </div>
)}
```

Pas de klassenamen aan naar de bestaande CSS/Tailwind conventies in het project.
Toon de secties alleen als de waarde aanwezig is (niet leeg).

---

## Acceptatiecriteria

- `GET /api/agents/{id}` retourneert `persona`, `qualities` en `development` als die beschikbaar zijn
- AgentDetail toont de drie secties op het Profiel tab
- Als een agent geen newbie_id match heeft: secties zijn gewoon niet zichtbaar
- NewbieDetail blijft ongewijzigd werken
- `npm run build` slaagt

---

## Wat je NIET doet

- Geen wijzigingen aan de newbies tabel of data
- Geen nieuwe API endpoints aanmaken
- Geen `git add -A`

---

## Commits na bevestiging

```bash
git add app/routes/agents.py
git commit -m "feat: include persona/qualities/development from newbies in agent response"

git add web_ui/frontend/src/AgentDetail.jsx
git commit -m "feat: toon persona, kwaliteiten en ontwikkelpunten op AgentDetail profiel tab"

git push
cd web_ui/frontend && npm run build
```
