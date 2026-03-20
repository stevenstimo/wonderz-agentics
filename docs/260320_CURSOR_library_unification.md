# Library Unification + Newbies Library Access
**Datum:** 20 maart 2026
**Feature:** `library_unification`
**Scope:** Backend (approve endpoint) + Frontend (Newbies Library tab)

> Dit document is de authoritative bron voor deze Cursor-sessie. Bij twijfel: dit document prevaleert boven aannames.

---

## Context

De HR Manager kan nu trainingsuggesties vinden en klaarzetten ter goedkeuring (`/hr/training-suggestions`). Na approve gaat de URL momenteel naar de agent training workflow (`TrainingWorkflow.start_training()`), die de content embedded in `agent_knowledge`.

**Wat nog ontbreekt:**
1. Na approve moet de bron ook zichtbaar worden in de Knowledge Library (`/knowledge`) zodat agents én newbies er gebruik van kunnen maken.
2. Newbies hebben nu geen toegang tot de Knowledge Library. Ze moeten die kunnen inzien vanuit hun eigen sectie.

**Gewenste eindstaat:**
```
HR approve training suggestion
    → bestaande training workflow (agent_knowledge, vectorstore) — ongewijzigd
    → NIEUW: INSERT in library-tabel zodat bron verschijnt op /knowledge

Newbies-pagina
    → NIEUW: Library-tab die /knowledge entries toont (read-only)
```

---

## Pre-flight checks — verplicht vóór elke code

Voer deze checks uit en rapporteer de uitkomst per stap. Stop bij een onverwacht resultaat.

```bash
# (terminal) 1. Zoek welke route /knowledge bedient
grep -r "knowledge" app/routes/ --include="*.py" -l
grep -r "/knowledge" app/routes/ --include="*.py" -n | head -20

# (terminal) 2. Zoek de tabel die Library-entries opslaat
grep -r "newbie_library\|knowledge_docs\|lessons\|library_entries" app/routes/ app/services/ --include="*.py" -n | head -30
```

```sql
-- (SQL) 3. Controleer welke tabellen library-achtige namen hebben
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name ILIKE '%library%'
  OR table_name ILIKE '%lesson%'
  OR table_name ILIKE '%knowledge_doc%'
ORDER BY table_name;

-- (SQL) 4. Toon kolommen van de gevonden library-tabel
-- Pas de tabelnaam aan op basis van uitkomst hierboven
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = '<library_tabel_naam>'
ORDER BY ordinal_position;

-- (SQL) 5. Controleer training_suggestions tabel (bestaat al)
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'training_suggestions'
ORDER BY ordinal_position;
```

**Rapporteer:**
- Exacte naam van de library-tabel die `/knowledge` bedient
- Alle kolommen van die tabel
- Of `training_suggestions` de kolom `development_point_ref` heeft (Optie B, bevestigd in productie)

Stop hier en wacht op bevestiging vóór fase 1.

---

## Fase 1 — Approve endpoint: INSERT in library na goedkeuring

**Bestand:** `app/routes/hr.py`
**Endpoint:** `POST /api/hr/training-suggestions/{suggestion_id}/approve`

Na de bestaande `TrainingWorkflow.start_training()` aanroep, voeg toe:

```python
# INSERT in library zodat bron zichtbaar wordt op /knowledge
try:
    await _insert_suggestion_into_library(conn, suggestion)
except Exception as e:
    print(f"[approve_suggestion] library insert fout: {e}")
    # Approve en training staan al — library insert is additioneel, nooit blocking
```

**Nieuwe helper in `app/routes/hr.py`:**

```python
async def _insert_suggestion_into_library(conn, suggestion: dict):
    """
    Voegt een goedgekeurde training suggestion in als Library entry.
    Gebruikt de exacte kolomnamen van de library-tabel (bepaald in pre-flight).
    Duplicate-safe via ON CONFLICT DO NOTHING op url-kolom indien aanwezig.
    """
    # Bepaal de juiste INSERT op basis van pre-flight kolomnamen.
    # Minimaal vereiste velden: title, url/source_url, status='approved', origin='hr_discovery'
    # Pas kolomnamen aan op werkelijke tabel-structuur.
    await conn.execute(
        """
        INSERT INTO <library_tabel> (title, source_url, summary, status, tags, created_at)
        VALUES ($1, $2, $3, 'approved', $4, now())
        ON CONFLICT (source_url) DO NOTHING
        """,
        suggestion.get("title") or suggestion.get("url"),
        suggestion["url"],
        suggestion.get("rationale", ""),
        ["hr-discovery"],
    )
```

**Belangrijk:**
- Pas `<library_tabel>` en kolomnamen aan op werkelijke uitkomst van pre-flight.
- `ON CONFLICT DO NOTHING` voorkomt duplicaten als dezelfde URL al in de library staat.
- Als de library-tabel geen `source_url` heeft maar bijv. `url`: pas aan.
- Als de library-tabel een verplicht veld heeft zonder default: voeg toe.
- De bestaande `TrainingWorkflow.start_training()` aanroep blijft ongewijzigd.

**Acceptatiecriteria fase 1:**
- [ ] Approve van een training suggestion maakt een entry aan in de library-tabel
- [ ] Entry verschijnt zichtbaar op `/knowledge` na approve
- [ ] Fout in library insert blokkeert de approve niet
- [ ] Geen duplicaten bij dubbele approve van zelfde URL

Rapporteer na fase 1 en wacht op bevestiging.

---

## Fase 2 — Newbies: Library-tab toevoegen

### 2.1 Scope

De Newbies-pagina (`/newbies` of een NewbieDetail component) krijgt een extra tab of sectie: **Kennisbronnen**. Deze toont de goedgekeurde entries uit de Library, read-only, zodat newbies kunnen leren van beschikbare bronnen.

Geen nieuwe routes, geen nieuwe tabellen. Newbies lezen via de bestaande Library-endpoints.

### 2.2 Bestaande Library endpoint

Zoek eerst het bestaande GET-endpoint voor de Library:

```bash
# (terminal)
grep -r "GET.*knowledge\|GET.*library\|GET.*lessons" app/routes/ --include="*.py" -n
```

Gebruik dat endpoint in de Newbies-frontend. Maak geen nieuw endpoint aan tenzij het bestaande endpoint auth vereist die newbies-context niet heeft.

### 2.3 Frontend: Kennisbronnen tab in Newbies

**Bestand:** `web_ui/frontend/src/NewbieDetail.jsx` of het hoofd Newbies-component (controleer welk component de Newbies-detailpagina rendert).

Voeg toe:
- Nieuw tabblad **Kennisbronnen** naast bestaande tabs (Profiel, Training, etc.)
- Toont Library-entries gefilterd op `status = 'approved'`
- Per entry: titel, URL (klikbaar, opent in nieuw tabblad), samenvatting/rationale, datum
- Zoekbalk op trefwoord (client-side filtering op titel/tags)
- Lege state: "Nog geen kennisbronnen beschikbaar."
- Geen approve/reject knoppen — dit is read-only voor newbies

### 2.4 API call

```javascript
// Gebruik bestaand library endpoint
GET /api/knowledge?status=approved
// of het equivalent dat /knowledge bedient
// Bepaal exacte URL op basis van pre-flight terminal check
```

### 2.5 useAuthReady guard

Verplicht in useEffect:
```javascript
useEffect(() => {
  if (!authReady) return;
  fetchLibraryEntries();
}, [authReady]);
```

**Acceptatiecriteria fase 2:**
- [ ] Newbies-pagina heeft een Kennisbronnen-tab
- [ ] Tab toont goedgekeurde Library-entries
- [ ] URL per entry is klikbaar en opent extern
- [ ] Zoeken/filteren werkt client-side
- [ ] `useAuthReady` guard aanwezig
- [ ] Read-only: geen acties beschikbaar voor newbies

Rapporteer na fase 2 en wacht op bevestiging.

---

## Wat je NIET doet

- Geen nieuwe library-tabel aanmaken — gebruik wat er al is
- Geen wijzigingen aan de bestaande training workflow voor agents
- Geen wijzigingen aan de Library-pagina zelf (`/knowledge`)
- Geen nieuwe API endpoints tenzij het bestaande endpoint onbruikbaar is
- Geen `git add -A` — stage altijd specifieke bestanden
- Geen Vercel deploy-suggesties
- Niet meerdere fases tegelijk uitvoeren

---

## Deployment na afronding

```bash
# (terminal) vanuit ~/wonderz-agentics
git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build
```

---

## Acceptatiecriteria totaal

- [ ] Approve van HR training suggestion → entry verschijnt op `/knowledge`
- [ ] Agents kunnen library-entries ophalen via bestaande `read_lessons` tool
- [ ] Newbies zien Kennisbronnen-tab op hun pagina
- [ ] Newbies kunnen library-entries lezen en URL's openen
- [ ] Geen dubbele entries bij herhaalde approve
- [ ] Fouten in library insert blokkeren de approve-flow niet
