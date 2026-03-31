# 260328_CURSOR_hiringhall_hire_flow

## Verplichte git-regels

- Nooit `git restore`, `git checkout --force`, `git reset` of `git clean` uitvoeren
- Bij elke git-operatie eerst `git status` rapporteren en wachten op bevestiging
- Alleen specifieke bestanden stagen, nooit `git add -A`

---

## Context

Wonderz-Agentics, React/Vite frontend + FastAPI backend.

De Hiring Hall (`/hiring-hall` of vergelijkbaar) toont beschikbare agent-presets. Als een gebruiker op een preset klikt met `?promote=<newbie_id>` in de URL, zou hij direct die newbie moeten kunnen aannemen in die rol. Dit `?promote=` patroon bestaat in de frontend maar de bijbehorende POST naar de backend ontbreekt of werkt niet.

Het `POST /api/newbies/{newbie_id}/hire` endpoint bestaat al en werkt (is eerder getest met Jules Winnfield).

---

## Pre-flight

```bash
# 1. Zoek de HiringHall component
find web_ui/frontend/src -name "*iring*" -o -name "*Hall*" -o -name "*hall*" 2>/dev/null

# 2. Zoek ?promote= gebruik in de frontend
grep -rn "promote" web_ui/frontend/src --include="*.jsx" | head -20

# 3. Check het hire endpoint
grep -rn "hire\|/hire" app/routes/newbies.py | head -10

# 4. Check hoe de HiringHall nu agents aanmaakt
grep -rn "POST\|fetch\|apiFetch" web_ui/frontend/src --include="*.jsx" | grep -i "hire\|hall\|preset" | head -10
```

Rapporteer de output. Ga direct door.

---

## Wat je bouwt

### Probleem

De `?promote=<newbie_id>` query parameter in de HiringHall URL wordt door de frontend gelezen maar er wordt geen echte POST naar het hire-endpoint gedaan. De gebruiker ziet wel de preset maar kan niet direct aannemen.

### Fix

In de HiringHall component:

1. **Lees de `?promote=` parameter uit de URL:**
```jsx
const [searchParams] = useSearchParams();
const promoteNewbieId = searchParams.get('promote');
```

2. **Als `promoteNewbieId` aanwezig is:** toon een banner of highlight bovenaan de pagina:
```
"Je neemt [Newbie naam] aan. Kies een preset om mee te starten."
```

3. **Als gebruiker op een preset klikt én `promoteNewbieId` aanwezig is:** doe een POST naar het hire endpoint:
```javascript
await apiFetch(`/api/newbies/${promoteNewbieId}/hire`, {
  method: 'POST',
  body: JSON.stringify({
    role: preset.role,           // rol uit de geselecteerde preset
    system_prompt: preset.system_prompt,  // system prompt uit preset
  })
}, session);
```

4. **Na succesvolle hire:** navigeer naar de agent pagina van de nieuwe agent:
```jsx
navigate(`/agents/${response.agent_id}`);
```

5. **Bij fout:** toon een inline foutmelding in de HiringHall pagina.

6. **Als geen `?promote=` aanwezig:** normaal gedrag — gebruiker kan preset bekijken en zelf een newbie selecteren of een nieuwe agent aanmaken.

### Backend check

Verifieer dat `POST /api/newbies/{newbie_id}/hire` de volgende velden accepteert:
- `role` — de rol die de agent krijgt
- `system_prompt` — optioneel, override van de standaard system prompt

Als het endpoint deze velden nog niet accepteert, voeg ze toe als optionele parameters.

---

## Acceptatiecriteria

- `/hiring-hall?promote=agent:talent:X` toont een duidelijke banner
- Klikken op een preset in promote-modus roept het hire endpoint aan
- Na succesvolle hire: redirect naar de agent pagina
- Zonder `?promote=`: normaal gedrag ongewijzigd
- `npm run build` slaagt

---

## Wat je NIET doet

- Geen wijzigingen aan de pipeline of orchestration
- Geen nieuwe DB tabellen
- Geen `git add -A`

---

## Commits na bevestiging

```bash
# Backend (alleen als hire endpoint aanpassing nodig is)
git add app/routes/newbies.py
git commit -m "feat: hire endpoint accepteert role en system_prompt override"

# Frontend
git add web_ui/frontend/src/HiringHall.jsx  # of de juiste bestandsnaam
git commit -m "feat: HiringHall ?promote= flow met hire POST en redirect"

git push
sudo systemctl restart wonderz-backend
cd web_ui/frontend && npm run build
```
