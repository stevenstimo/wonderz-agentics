# 260314 — Code Splitting & useAuthReady Audit
**Doel:** Paginalaadtijd verbeteren via lazy loading en auth-race conditions elimineren.

---

## Context

De huidige build produceert één bundle van ~1.2MB:
```
dist/assets/index.js   1,208.98 kB │ gzip: 324.60 kB
(!) Some chunks are larger than 500 kB after minification.
```

Vite heeft dit meerdere keren gewaarschuwd. Elke paginanavigatie laadt de volledige app opnieuw in.

Daarnaast hebben meerdere pagina's een hard refresh nodig om correct te laden. Oorzaak: componenten fetchen data bij mount zonder te wachten tot de auth-state beschikbaar is (`useAuthReady` ontbreekt of is inconsistent toegepast).

---

## Pre-flight checks

Voer deze controles uit vóór je begint. Stop bij elke fout en meld wat er mis is.

```bash
# 1. Huidige bundle grootte
cd web_ui/frontend && npm run build 2>&1 | grep "dist/assets"

# 2. Welke pagina's gebruiken useAuthReady al correct?
grep -rn "useAuthReady" src/ --include="*.jsx" --include="*.tsx"

# 3. Welke pagina's doen een apiFetch/fetch direct in useEffect zonder auth-check?
grep -rn "useEffect" src/pages/ --include="*.jsx" -l

# 4. Huidige routes in main.jsx
grep -n "element=" src/main.jsx | head -30
```

Rapporteer de output van alle vier checks vóór je verder gaat.

---

## Fase 1 — Lazy loading instellen in main.jsx

**Wat:** Vervang alle directe imports van pagina-componenten door `React.lazy()`. Elke pagina wordt een aparte chunk die alleen ingeladen wordt bij navigatie.

**Hoe:**

```jsx
// VOOR (directe import — alles in één bundle)
import HRDashboard from './pages/HRDashboard'
import AgentsOverview from './pages/AgentsOverview'
// etc.

// NA (lazy import — aparte chunk per pagina)
import { lazy, Suspense } from 'react'
const HRDashboard = lazy(() => import('./pages/HRDashboard'))
const AgentsOverview = lazy(() => import('./pages/AgentsOverview'))
// etc.
```

Wikkel de `<Routes>` in een `<Suspense>` fallback:

```jsx
<Suspense fallback={<div className="flex items-center justify-center h-screen text-sm text-gray-400">Laden...</div>}>
  <Routes>
    {/* alle routes blijven exact hetzelfde */}
  </Routes>
</Suspense>
```

**Regels:**
- Lazy loading alleen voor pagina-componenten (alles in `src/pages/`).
- Gedeelde componenten zoals `Sidebar`, `TopHeader`, `RequireAuth` blijven directe imports.
- Verwijder geen bestaande routes of componenten.
- Voeg geen nieuwe logica toe buiten lazy/Suspense.

**Acceptatiecriterium fase 1:**
```bash
npm run build 2>&1 | grep "dist/assets"
# Verwacht: meerdere kleinere JS-bestanden in plaats van één groot bestand
# Elk paginabestand kleiner dan 200 kB
```

Stop hier. Rapporteer de nieuwe bundle output vóór je naar fase 2 gaat.

---

## Fase 2 — useAuthReady audit en fix

**Wat:** Controleer systematisch welke pagina's data fetchen zonder te wachten op auth. Voeg `useAuthReady` toe waar het ontbreekt.

**Patroon dat fout is:**
```jsx
// FOUT: fetch start direct, sessie is mogelijk nog niet beschikbaar
useEffect(() => {
  apiFetch('/api/agents').then(...)
}, [])
```

**Correct patroon:**
```jsx
import { useAuthReady } from '../hooks/useAuthReady'

const authReady = useAuthReady()

useEffect(() => {
  if (!authReady) return  // wacht op auth
  apiFetch('/api/agents').then(...)
}, [authReady])
```

**Stappenplan:**
1. Lijst alle bestanden in `src/pages/` die `apiFetch` of `fetch` aanroepen in een `useEffect`.
2. Check per bestand of `useAuthReady` al aanwezig is en correct toegepast.
3. Voeg `useAuthReady` toe aan elk bestand waar het ontbreekt.
4. Zorg dat elke `useEffect` die data ophaalt `authReady` in de dependency array heeft en vroeg returnt als `!authReady`.

**Wat je NIET doet:**
- Geen wijzigingen aan `useAuthReady.js` zelf.
- Geen wijzigingen aan `RequireAuth.jsx`.
- Geen refactor van de fetch-logica zelf, alleen de auth-guard toevoegen.

**Acceptatiecriterium fase 2:**
```bash
grep -rn "useAuthReady" src/pages/ --include="*.jsx"
# Verwacht: aanwezig in elk bestand dat apiFetch aanroept
```

Stop hier. Rapporteer welke bestanden zijn aangepast vóór je naar fase 3 gaat.

---

## Fase 3 — Vite chunking configuratie (optioneel, alleen als fase 1 nog grote chunks geeft)

Als na fase 1 nog steeds één of meer chunks groter dan 500 kB zijn, voeg dan handmatige chunking toe in `vite.config.js`:

```js
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        vendor: ['react', 'react-dom', 'react-router-dom'],
        supabase: ['@supabase/supabase-js'],
      }
    }
  }
}
```

Voer daarna opnieuw `npm run build` uit en rapporteer de nieuwe bundle output.

---

## Fase 4 — Bouwen en deployen

```bash
# (terminal) op de server
cd ~/wonderz-agentics/web_ui/frontend && npm run build
sudo systemctl restart wonderz-backend
```

Test daarna handmatig:
1. Navigeer naar `/hr` — laadt zonder hard refresh?
2. Navigeer naar `/agents` — laadt zonder hard refresh?
3. Navigeer naar `/seo` — laadt zonder hard refresh?
4. Open DevTools → Network tab: worden aparte JS-chunks ingeladen per pagina?

Rapporteer de testresultaten.

---

## Wat je NIET doet

- Geen wijzigingen aan de routestructuur.
- Geen nieuwe features of UI-aanpassingen.
- Geen wijzigingen aan backend-code.
- Geen aanpassingen aan authenticatielogica buiten het toevoegen van `useAuthReady`.
