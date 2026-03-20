# 260320 — Frontend fixes: Kennis detail view, Spinner HR modal, Console logs handleApprove, Progress bar RUNNING

**Versie:** 1.0  
**Datum:** 20 maart 2026  
**Scope:** Vier gerichte frontend fixes, één commit.

---

## Pre-flight

```bash
# 1. Relevante componenten lokaliseren
find web_ui/frontend/src -name "*.jsx" | xargs grep -l "handleApprove\|KennisDetail\|HRDashboard\|RUNNING\|progress" 2>/dev/null

# 2. Console.log aanroepen in handleApprove vinden
grep -rn "console.log" web_ui/frontend/src --include="*.jsx" | grep -i "approve"

# 3. HR modal spinner locatie
grep -rn "modal\|spinner\|loading" web_ui/frontend/src --include="*.jsx" | grep -i "hr\|training\|approve" | head -20

# 4. Progress bar RUNNING locatie
grep -rn "RUNNING\|progress" web_ui/frontend/src --include="*.jsx" | head -20
```

Rapporteer de output. Dan pas uitvoeren.

---

## Item 1 — Kennis detail view

### Wat ontbreekt

Er is een kennislijst maar geen detail view. Als een gebruiker op een kennisitem klikt, moet er een detailpagina of sidepanel openen met de volledige inhoud van dat item.

### Wat bouwen

**Zoek eerst:**
- Hoe de kennislijst nu gerenderd wordt (component naam, route)
- Wat het datamodel is van een kennisitem (velden die al beschikbaar zijn via de API)
- Of er al een `GET /api/knowledge/{id}` endpoint bestaat

**Bouw dan:**

1. Een `KennisDetail` component (of sidepanel, afhankelijk van de bestaande UI structuur) dat toont:
   - Titel / naam van het item
   - Bron URL (als aanwezig)
   - Volledige tekst / samenvatting
   - Metadata: aangemaakt op, agent_id, status
   - Knop "Sluiten" (of terug naar lijst)

2. Koppel het aan de bestaande kennislijst: klik op een rij → detail view opent.

3. Gebruik `useAuthReady` guard in de data fetch.

**Regels:**
- Geen nieuwe route aanmaken als een sidepanel past binnen de bestaande layout
- Geen nieuwe dependencies
- Gebruik bestaande stijlen

**Acceptatiecriteria:**
- [ ] Klikken op een kennisitem toont de detail view
- [ ] Alle beschikbare velden worden getoond
- [ ] Sluiten werkt en keert terug naar de lijst
- [ ] Geen console errors

---

## Item 2 — Spinner HR modal

### Wat ontbreekt

De HR modal (voor het goedkeuren of afwijzen van trainingsverzoeken) toont geen laadspinner terwijl een actie wordt verwerkt. Dit geeft de indruk dat de knop niet werkt, en maakt dubbel klikken mogelijk.

### Wat bouwen

Zoek de HR approval modal component. Voeg toe:

1. **Loading state:** een `isSubmitting` boolean state, default `false`.

2. **Bij klikken op Goedkeuren of Afwijzen:**
   - Zet `isSubmitting = true`
   - Disable beide knoppen (`disabled={isSubmitting}`)
   - Toon een inline spinner naast de knoptekst:
     ```jsx
     {isSubmitting ? (
       <span className="spinner" aria-label="Laden..." />
     ) : (
       "Goedkeuren"
     )}
     ```
   - Na response (succes of fout): zet `isSubmitting = false`

3. **Spinner CSS** (voeg toe aan de bestaande stylesheet of inline):
   ```css
   .spinner {
     display: inline-block;
     width: 14px;
     height: 14px;
     border: 2px solid rgba(255,255,255,0.3);
     border-top-color: white;
     border-radius: 50%;
     animation: spin 0.6s linear infinite;
     margin-right: 6px;
     vertical-align: middle;
   }
   @keyframes spin {
     to { transform: rotate(360deg); }
   }
   ```

4. **Error handling:** als de API call faalt, toon een inline foutmelding in de modal (niet alleen een console.error). Zet `isSubmitting = false` zodat de gebruiker opnieuw kan proberen.

**Acceptatiecriteria:**
- [ ] Spinner zichtbaar tijdens verwerking
- [ ] Knoppen disabled tijdens verwerking (geen dubbele submit mogelijk)
- [ ] Na succes: modal sluit, lijst refresht
- [ ] Na fout: foutmelding zichtbaar, knoppen weer enabled
- [ ] Geen console errors

---

## Item 3 — Console logs handleApprove verwijderen

### Wat ontbreekt

`handleApprove` (en mogelijk `handleFeedback`) bevatten `console.log` statements die niet in productie horen.

### Wat doen

1. Zoek alle `console.log` aanroepen in of rond `handleApprove` en `handleFeedback` in de frontend.

2. Verwijder alle `console.log` en `console.error` statements die debug-informatie loggen (bijv. response bodies, job IDs, status updates).

3. **Uitzondering:** als er een `console.error` is die een echte fout logt die nergens anders zichtbaar wordt voor de gebruiker, vervang die door een zichtbare UI-melding (inline error state) en verwijder dan de console.error.

4. **Niet aanraken:** bestaande error boundaries of logging die buiten handleApprove/handleFeedback staat.

**Acceptatiecriteria:**
- [ ] Geen `console.log` meer in handleApprove en handleFeedback
- [ ] Fouten die eerder alleen gelogd werden zijn nu zichtbaar als UI-melding
- [ ] Functionaliteit onveranderd

---

## Item 4 — Progress bar bij RUNNING status

### Wat ontbreekt

Als een job op `RUNNING` staat ziet de gebruiker geen visuele voortgang. De UI geeft geen indicatie dat er iets gaande is.

### Wat bouwen

Zoek de component die de RUNNING status toont (vermoedelijk `JobDetail.jsx`, `LiveTracker.jsx` of vergelijkbaar).

Voeg toe:

1. **Geanimeerde progress bar** die zichtbaar is alleen als `job.status === 'RUNNING'`:

```jsx
{job.status === 'RUNNING' && (
  <div className="progress-bar-container">
    <div className="progress-bar-indeterminate" />
  </div>
)}
```

2. **CSS** (indeterminate, dus geen percentage nodig):
```css
.progress-bar-container {
  width: 100%;
  height: 4px;
  background: #e5e7eb;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 12px;
}

.progress-bar-indeterminate {
  height: 100%;
  width: 40%;
  background: #6366f1;
  border-radius: 2px;
  animation: progress-slide 1.4s ease-in-out infinite;
}

@keyframes progress-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}
```

3. **Positie:** direct boven of onder de status badge, binnen de bestaande RUNNING-weergave. Niet in de header, niet over andere content.

4. **Verdwijnt automatisch** als de status verandert naar iets anders dan RUNNING (via de bestaande polling).

**Acceptatiecriteria:**
- [ ] Progress bar zichtbaar bij RUNNING
- [ ] Progress bar verdwijnt bij andere statussen
- [ ] Pure CSS animatie, geen JS interval
- [ ] Geen regressie op andere statussen

---

## Wat je NIET doet

- Geen nieuwe npm packages installeren
- Geen wijzigingen aan routing of layout buiten de genoemde componenten
- Geen backend wijzigingen
- Geen WebSocket implementatie
- Geen `git add -A` — stage alleen de bestanden die je hebt aangeraakt

---

## Commit

```bash
# Stage exact de bestanden die je hebt aangepast (pas aan op basis van wat je gevonden hebt)
git add web_ui/frontend/src/pages/KennisDetail.jsx        # of de gevonden locatie
git add web_ui/frontend/src/components/HRModal.jsx        # of de gevonden locatie
git add web_ui/frontend/src/pages/JobDetail.jsx           # of de gevonden locatie
git add web_ui/frontend/src/components/LiveTracker.jsx    # of de gevonden locatie
# voeg toe wat je daadwerkelijk hebt aangepast

git commit -m "feat(frontend): kennis detail view, HR modal spinner, remove console logs, RUNNING progress bar"
```

Daarna deployen:

```bash
cd web_ui/frontend && npm run build
```

---

## Acceptatiecriteria (totaalcheck)

- [ ] Klikken op kennisitem toont detail view
- [ ] HR modal toont spinner en disabled knoppen tijdens verwerking
- [ ] Geen console.log meer in handleApprove / handleFeedback
- [ ] Progress bar zichtbaar bij RUNNING, verdwijnt bij andere statussen
- [ ] Geen console errors in de browser na alle vier fixes
- [ ] `npm run build` slaagt zonder warnings over de gewijzigde bestanden
