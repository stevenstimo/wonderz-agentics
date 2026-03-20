# 260320 — TanStack Query migratie

**Versie:** 1.0  
**Datum:** 20 maart 2026  
**Scope:** Migratie van handmatige `useEffect` + `fetch` + eigen loading/error state naar TanStack Query (`@tanstack/react-query`) in de volledige frontend.

---

## Waarom deze migratie

De huidige frontend doet data fetching handmatig in elk component:
- `useEffect` + `fetch` + `useState` voor loading/error/data in elk component apart
- `setInterval` polling voor job-status updates (10 bestanden)
- Geen caching: elke navigatie triggert opnieuw een fetch
- Geen deduplicatie: meerdere componenten fetchen dezelfde data onafhankelijk
- Inconsistente error handling per component

TanStack Query centraliseert dit: automatische caching, background refetching, `refetchInterval` als vervanging voor `setInterval`, loading/error states out of the box.

**Belangrijk:** Na deze migratie is de PDF v2 rebuild (jspdf → @react-pdf/renderer) haalbaar op een stabiele data-laag.

---

## Pre-flight

```bash
# 1. Huidige fetch-patronen in kaart brengen
grep -rn "useEffect\|useState.*loading\|useState.*error\|setInterval" \
  web_ui/frontend/src --include="*.jsx" | grep -v "node_modules" | wc -l

# 2. Exact welke bestanden setInterval gebruiken (polling)
grep -rln "setInterval" web_ui/frontend/src --include="*.jsx"

# 3. Exact welke bestanden useEffect + fetch gebruiken
grep -rln "useEffect" web_ui/frontend/src --include="*.jsx"

# 4. Is @tanstack/react-query al geïnstalleerd?
cat web_ui/frontend/package.json | grep tanstack

# 5. Waar staat de app root (voor QueryClientProvider)
grep -rn "ReactDOM\|createRoot\|App\b" web_ui/frontend/src/main.jsx 2>/dev/null || \
grep -rn "ReactDOM\|createRoot" web_ui/frontend/src/index.jsx 2>/dev/null
```

Rapporteer de volledige output van elke check. Dan pas uitvoeren.

---

## Fasering

Werk fasen strikt in volgorde. Na elke fase: rapporteer en wacht op bevestiging.

| Fase | Beschrijving | Risico |
|------|-------------|--------|
| 1 | Installatie + QueryClientProvider | Geen |
| 2 | Centrale query keys + API helpers | Geen |
| 3 | Migreer eenvoudige lijstpagina's (agents, clients, knowledge) | Laag |
| 4 | Migreer job-gerelateerde components (polling vervangen) | Medium |
| 5 | Migreer HR Dashboard | Medium |
| 6 | Opruimen: verwijder overgebleven handmatige fetch-patronen | Laag |

---

## Fase 1 — Installatie + QueryClientProvider

### 1.1 Installeren

```bash
cd web_ui/frontend
npm install @tanstack/react-query
```

Voeg toe aan `package.json` dependencies (wordt automatisch gedaan door npm install).

### 1.2 QueryClientProvider instellen

Zoek het root-bestand (`main.jsx` of `index.jsx`). Wrap de app:

```jsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // 30 seconden: data is vers, geen refetch bij navigatie
      retry: 1,                  // bij fout 1x retry
      refetchOnWindowFocus: false, // geen refetch bij tab-switch (storend bij forms)
    },
  },
});

// In de render:
<QueryClientProvider client={queryClient}>
  <App />
</QueryClientProvider>
```

**Fase 1 gereed als:** `npm run build` slaagt, geen import errors.

---

## Fase 2 — Centrale query keys + API helpers

### 2.1 Query keys bestand

Maak `web_ui/frontend/src/queryKeys.js` aan:

```javascript
// Centrale definitie van alle query keys.
// Hiermee voorkomen we typo's en maken we cache-invalidation voorspelbaar.

export const queryKeys = {
  // Agents
  agents: () => ['agents'],
  agent: (id) => ['agents', id],

  // Jobs
  jobs: () => ['jobs'],
  job: (id) => ['jobs', id],
  jobSteps: (jobId) => ['jobs', jobId, 'steps'],

  // Clients
  clients: () => ['clients'],
  client: (id) => ['clients', id],

  // Knowledge
  knowledge: () => ['knowledge'],
  knowledgeItem: (id) => ['knowledge', id],

  // HR
  hrReport: () => ['hr', 'report'],
  developmentPoints: () => ['hr', 'development-points'],
  trainingRequests: () => ['hr', 'training-requests'],

  // SEO
  seoJobs: () => ['seo', 'jobs'],
  seoJob: (id) => ['seo', 'jobs', id],
};
```

### 2.2 API helpers bestand

Maak `web_ui/frontend/src/api.js` aan (of voeg toe aan een bestaand api-bestand):

```javascript
// Centrale API helper die de Authorization header toevoegt.
// Alle useQuery/useMutation calls gebruiken dit.

const BASE_URL = import.meta.env.VITE_API_URL || '';

export async function apiFetch(path, options = {}, session) {
  const headers = {
    'Content-Type': 'application/json',
    ...(session?.access_token
      ? { Authorization: `Bearer ${session.access_token}` }
      : {}),
    ...options.headers,
  };

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = new Error(`API fout: ${response.status} ${response.statusText}`);
    error.status = response.status;
    throw error;
  }

  return response.json();
}
```

**Fase 2 gereed als:** Bestanden aangemaakt, geen linting errors.

---

## Fase 3 — Migreer eenvoudige lijstpagina's

Migreer de volgende componenten van handmatig `useEffect + fetch` naar `useQuery`. Dit zijn de eenvoudigste componenten: één fetch, geen polling, geen mutations.

**Doelcomponenten (pas aan op basis van pre-flight):**
- Agents overzicht
- Clients overzicht
- Knowledge lijst

### 3.1 Migratiepatroon

**Oud patroon:**
```jsx
const [agents, setAgents] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);
const { authReady, session } = useAuthReady();

useEffect(() => {
  if (!authReady) return;
  fetch('/api/agents', {
    headers: { Authorization: `Bearer ${session.access_token}` }
  })
    .then(r => r.json())
    .then(data => { setAgents(data.agents); setLoading(false); })
    .catch(err => { setError(err); setLoading(false); });
}, [authReady]);
```

**Nieuw patroon:**
```jsx
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../queryKeys';
import { apiFetch } from '../api';

const { authReady, session } = useAuthReady();

const { data, isLoading, error } = useQuery({
  queryKey: queryKeys.agents(),
  queryFn: () => apiFetch('/api/agents', {}, session),
  enabled: authReady,   // vervangt de `if (!authReady) return;` guard
  select: (data) => data.agents,  // extraheer de array direct
});

// In de render:
if (isLoading) return <Spinner />;
if (error) return <ErrorMessage error={error} />;
// data is nu direct de agents array
```

### 3.2 Regels voor fase 3

- Verwijder de handmatige `useState` voor loading/error/data als `useQuery` die vervangt
- Behoud `useAuthReady` — de `enabled: authReady` regel vervangt de `if (!authReady) return;` in useEffect
- Verwijder de `useEffect` die de fetch deed
- Behoud alle andere `useEffect` calls die niets met data fetching te maken hebben

**Fase 3 gereed als:** Drie componenten gemigreerd, `npm run build` slaagt, pagina's laden correct in browser.

---

## Fase 4 — Migreer job-gerelateerde components (polling)

Dit is de kernmigratie: `setInterval` polling vervangen door TanStack Query's `refetchInterval`.

**Doelcomponenten (op basis van pre-flight):**
- `Sidebar.jsx`
- `Dashboard.jsx`
- `JobDetail.jsx`
- `JobFlow.jsx` (of vergelijkbaar)
- `TopHeader.jsx`
- `JobCenter.jsx`
- `JobSplitView.jsx`

### 4.1 Polling migratiepatroon

**Oud patroon:**
```jsx
useEffect(() => {
  if (!authReady) return;
  const interval = setInterval(() => {
    fetch(`/api/jobs/${jobId}`)
      .then(r => r.json())
      .then(setJob);
  }, 2000);
  return () => clearInterval(interval);
}, [authReady, jobId]);
```

**Nieuw patroon:**
```jsx
const { data: job } = useQuery({
  queryKey: queryKeys.job(jobId),
  queryFn: () => apiFetch(`/api/jobs/${jobId}`, {}, session),
  enabled: authReady && !!jobId,
  refetchInterval: (query) => {
    // Alleen pollen als de job actief is
    const status = query.state.data?.status;
    if (['RUNNING', 'INTAKE_CLARIFICATION', 'PLAN_PROPOSED'].includes(status)) {
      return 2000; // elke 2 seconden
    }
    return false; // stop polling bij eindstatus
  },
  select: (data) => data.job ?? data, // flexibel voor verschillende response shapes
});
```

### 4.2 Mutations voor job-acties

Job-acties (approve, feedback, start) worden `useMutation`:

```jsx
import { useMutation, useQueryClient } from '@tanstack/react-query';

const queryClient = useQueryClient();

const approveMutation = useMutation({
  mutationFn: () => apiFetch(`/api/jobs/${jobId}/approve`, { method: 'POST' }, session),
  onSuccess: () => {
    // Invalideer de job query zodat hij opnieuw gefetcht wordt
    queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
  },
});

// In de render:
<button
  onClick={() => approveMutation.mutate()}
  disabled={approveMutation.isPending}
>
  {approveMutation.isPending ? <Spinner /> : 'Approve'}
</button>
```

### 4.3 Regels voor fase 4

- Elke `setInterval` wordt een `refetchInterval` in `useQuery`
- Elke `clearInterval` vervalt (TanStack beheert de cleanup)
- Job-mutaties (approve, feedback, reject) worden `useMutation` met `invalidateQueries` na succes
- `isSubmitting` state in modals wordt `mutation.isPending`

**Fase 4 gereed als:** Alle polling-bestanden gemigreerd, job flow werkt end-to-end, `npm run build` slaagt.

---

## Fase 5 — Migreer HR Dashboard

HR Dashboard heeft zowel queries (lijsten) als mutations (approve/reject acties).

**Patroon:** zelfde als fase 3 + 4 gecombineerd.

```jsx
// Queries
const { data: devPoints } = useQuery({
  queryKey: queryKeys.developmentPoints(),
  queryFn: () => apiFetch('/api/hr/development-points', {}, session),
  enabled: authReady,
});

const { data: trainingRequests } = useQuery({
  queryKey: queryKeys.trainingRequests(),
  queryFn: () => apiFetch('/api/hr/training-requests?status=PENDING', {}, session),
  enabled: authReady,
});

// Mutation: approve training
const approveMutation = useMutation({
  mutationFn: (payload) => apiFetch('/api/hr/approve-training', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, session),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.trainingRequests() });
  },
});
```

**Fase 5 gereed als:** HR Dashboard laadt, approve/reject werken, spinner via `approveMutation.isPending`.

---

## Fase 6 — Opruimen

Na alle migraties:

1. Zoek overgebleven handmatige fetch-patronen:
```bash
grep -rn "useState.*loading.*true\|setLoading\|setError.*null" \
  web_ui/frontend/src --include="*.jsx"
```

2. Verwijder overgebleven `useState` voor loading/error/data die nu door TanStack worden beheerd.

3. Verwijder overgebleven lege `useEffect` calls (die alleen de fetch bevatten en na migratie leeg zijn).

4. Verifieer finale build:
```bash
npm run build
```

**Fase 6 gereed als:** Geen handmatige loading/error state meer voor data fetches, build slaagt.

---

## Wat je NIET doet

- Geen `useEffect` verwijderen die niet aan data fetching gerelateerd zijn (bijv. scroll handlers, event listeners, animaties)
- Geen backend wijzigingen
- Geen WebSocket implementatie — dat is item 5 en komt na deze migratie
- Geen `git add -A` — stage alleen de gewijzigde frontend bestanden
- Niet alle fasen tegelijk uitvoeren — na elke fase stoppen en rapporteren

---

## Commit (na fase 6)

```bash
git add web_ui/frontend/package.json
git add web_ui/frontend/package-lock.json
git add web_ui/frontend/src/main.jsx          # of index.jsx
git add web_ui/frontend/src/queryKeys.js
git add web_ui/frontend/src/api.js
git add web_ui/frontend/src/                  # alle gewijzigde componenten

git commit -m "feat(frontend): migreer data fetching naar TanStack Query, vervang setInterval polling door refetchInterval"
```

Deploy:
```bash
cd web_ui/frontend && npm run build
sudo systemctl restart wonderz-backend
```

---

## Acceptatiecriteria totaalcheck

- [ ] `@tanstack/react-query` aanwezig in `package.json`
- [ ] `QueryClientProvider` in app root
- [ ] Geen `setInterval` meer voor data polling in frontend
- [ ] Alle lijstpagina's laden via `useQuery`
- [ ] Job polling werkt via `refetchInterval` (stopt automatisch bij eindstatus)
- [ ] Approve/reject acties via `useMutation` met `invalidateQueries`
- [ ] `isSubmitting` state in modals vervangen door `mutation.isPending`
- [ ] `npm run build` slaagt zonder errors
- [ ] Geen regressie: alle bestaande flows werken na migratie
