# 260319 — Newbies: Autonome URL Evaluatie

**Datum:** 19 maart 2026  
**Systeem:** Wonderz Agentics  
**Scope:** Backend `app/routes/newbies.py` + Frontend `web_ui/frontend/src/Newbies.jsx`  
**Doel:** Newbie evalueert zelf of een URL relevant is en kiest zelf de categorie — gebruiker kiest niets meer.

---

## Context

De huidige Train-modal heeft twee inputs: een URL-textarea en een categorie-dropdown. De gebruiker bepaalt de categorie.

**Gewenste situatie:** Gebruiker gooit een URL in. De Newbie (via Claude API, op basis van zijn persona + qualities) besluit zelf:
1. Is dit relevant voor mij?
2. In welke categorie past dit het best?
3. Leg uit waarom.

De gebruiker ziet de beslissing en kan bevestigen. Geen handmatige categorie meer.

---

## Pre-flight checks (verplicht VOOR je begint)

Voer eerst uit, rapporteer de output:

```bash
# (terminal) Huidige staat van newbies routes
grep -n "def.*train\|def.*evaluate\|async def" ~/wonderz-agentics/app/routes/newbies.py | head -30
```

```bash
# (terminal) Categorie velden in de newbies tabel
grep -n "category\|management\|creative\|development\|operations" ~/wonderz-agentics/app/routes/newbies.py | head -20
```

```bash
# (terminal) Huidige Train modal in frontend
grep -n "categor\|train\|submit" ~/wonderz-agentics/web_ui/frontend/src/Newbies.jsx | head -30
```

```sql
-- (SQL) Supabase: check newbies tabel kolommen
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'newbies'
ORDER BY ordinal_position;
```

```sql
-- (SQL) Check newbie_trainings kolommen
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'newbie_trainings'
ORDER BY ordinal_position;
```

Stop na pre-flight. Rapporteer findings. Ga pas verder na groen licht.

---

## Architectuur — wat er gebouwd wordt

### Nieuw backend endpoint: `POST /api/newbies/{id}/evaluate`

Dit endpoint doet drie dingen sequentieel:
1. Scrape de URL (hergebruik bestaande scrape-logica)
2. Stuur content + newbie persona naar Claude API
3. Claude retourneert evaluatie-JSON
4. Als `accept: true`: start training in de gekozen categorie (hergebruik `_try_train_one_url`)
5. Return evaluatie + trainingsresultaat aan frontend

**Evaluatie-payload die Claude teruggeeft (strikt JSON, geen markdown):**
```json
{
  "accept": true,
  "category": "management",
  "reason": "Dit artikel over tijdmanagement sluit direct aan bij mijn kwaliteiten als spanningsdemper en mijn rol in operationele ondersteuning.",
  "confidence": 0.87
}
```

**Claude system prompt voor de evaluatie (injecteren als system message):**
```
Je bent {newbie_name}, een agent in ontwikkeling.

Jouw persona: {persona}
Jouw kwaliteiten: {qualities}
Jouw ontwikkelrichting: {development}

Je hebt net de inhoud van een webpagina gelezen.
Bepaal of deze inhoud relevant is voor jouw ontwikkeling als agent.

Beschikbare categorieën:
- management: leiderschap, planning, delegatie, communicatie
- creative: schrijven, design, storytelling, content
- development: techniek, code, architectuur, data
- operations: uitvoering, processen, ondersteuning, organisatie

Beantwoord ALLEEN met een JSON object. Geen markdown, geen uitleg erbuiten:
{
  "accept": true/false,
  "category": "management|creative|development|operations",
  "reason": "Jouw motivatie in eerste persoon (max 2 zinnen)",
  "confidence": 0.0-1.0
}

Als de inhoud niet te scrapen was, niet relevant is, of van lage kwaliteit is: accept = false.
```

### Backend implementatie

```python
# In app/routes/newbies.py

class EvaluateUrlRequest(BaseModel):
    source_url: str

@router.post("/{newbie_id}/evaluate")
async def evaluate_and_train_url(
    newbie_id: str,
    body: EvaluateUrlRequest,
    conn=Depends(get_db)
):
    """
    Newbie evalueert zelf een URL en besluit of hij traint.
    Combineert evaluatie + training in één call.
    """
    # 1. Haal newbie op (persona, qualities, development, naam)
    # 2. Scrape URL (hergebruik bestaande scrape-functie)
    # 3. Claude evaluatie call (system + user message)
    # 4. Parse JSON response (try/except, fallback accept=False)
    # 5. Als accept=True: roep _try_train_one_url aan met gekozen category
    # 6. Return: { evaluation: {...}, trained: bool, score_gained: int }
```

**Foutafhandeling:**
- Scrape mislukt → `{ accept: false, reason: "URL niet bereikbaar", confidence: 0 }`
- Claude geeft geen valid JSON → `{ accept: false, reason: "Kon inhoud niet beoordelen", confidence: 0 }`
- Training mislukt na accept=true → `{ accept: true, trained: false, error: "Training mislukt" }`

### Bestaand `train` endpoint blijft intact

Het bestaande `POST /api/newbies/{id}/train` endpoint wordt NIET verwijderd. Backwards compat blijft. Het nieuwe endpoint is `/evaluate` — een additionele route.

---

## Frontend aanpassingen — `Newbies.jsx`

### Train modal: nieuwe flow

**Voor (nu):**
- Textarea: URLs (één per regel)
- Dropdown: categorie kiezen
- Knop: Train

**Na:**
- Textarea: URLs (één per regel)
- Geen categorie dropdown meer
- Knop: "Laat [naam] evalueren"

### Evaluatie flow per URL:

```
Stap 1: "Evaluating URL 1 van 3..."
   → POST /api/newbies/{id}/evaluate met { source_url: url }
   → Wacht op response

Stap 2a (accept=true):
   "✓ Donna neemt dit aan — Management (87% zeker)"
   "Tijdmanagement past direct bij mijn rol als ondersteuner."
   → Score update via fetchNewbies()

Stap 2b (accept=false):
   "✗ Donna slaat dit over — niet relevant voor haar ontwikkeling"
   → Geen training, doorgaan naar volgende URL
```

### State die je nodig hebt:

```jsx
const [evaluationResults, setEvaluationResults] = useState([]); 
// Array van { url, accept, category, reason, confidence, trained, score_gained }

const [evaluationProgress, setEvaluationProgress] = useState(null);
// { current: 2, total: 5 } of null
```

### Resultaten tonen in modal (na evaluatie):

Per URL een rij:
- ✓ groen: "[URL] → Management (+10)"
- ✗ rood: "[URL] → overgeslagen (reden)"

Score bars in de card updaten na elke geaccepteerde URL (hergebruik bestaande `fetchNewbies(true)` call).

---

## Wat je NIET doet

- Geen wijzigingen aan het bestaande `/train` endpoint
- Geen wijzigingen aan andere routes of pagina's
- Geen `git add -A` — alleen specifiek stagen:
  `git add app/routes/newbies.py web_ui/frontend/src/Newbies.jsx`
- Geen Vercel deploy — frontend altijd via `npm run build` op de server

---

## Deployment na implementatie

```bash
# (terminal) vanuit ~/wonderz-agentics
git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build && cd ../..
```

---

## Acceptatiecriteria

- [ ] `POST /api/newbies/{id}/evaluate` bestaat en werkt
- [ ] Categorie dropdown is verdwenen uit Train modal
- [ ] Per URL: evaluatie response van Claude (accept/reject + reden)
- [ ] Bij accept=true: training wordt automatisch gestart in de gekozen categorie
- [ ] Score bars updaten live na elke geaccepteerde URL
- [ ] 403/404 URLs worden afgehandeld als `accept: false` zonder crash
- [ ] Bestaand `/train` endpoint werkt nog (niet aangeraakt)

---

## Rapportage per fase

Rapporteer na:
1. Pre-flight output
2. Backend endpoint gebouwd (toon de implementatie)
3. Frontend modal aangepast (toon de JSX wijzigingen)
4. Deploy + eerste test met een echte URL

Stop na stap 1 en wacht op groen licht.
