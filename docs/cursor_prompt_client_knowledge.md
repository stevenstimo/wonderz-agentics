# CURSOR PROMPT — Client Knowledge Hub
**Feature:** Kennisbeheer per client (website, tekst, PDF, CSV, product feed)
**Prioriteit:** Hoog
**Geschatte tijd:** 6-7 uur
**Vervangt:** cursor_prompt_client_crawler.md (volledig herschreven)

---

## Doel

Per client kunnen meerdere databronnen worden toegevoegd. Elke databron heeft een naam en een type. Alle bronnen worden gechunkt, geëmbed via BGE-M3 en opgeslagen in `client_knowledge`. De CEO injecteert automatisch relevante chunks als `@clientnaam` in een job wordt gebruikt.

**Vijf brontypen:**
| Type | Invoer | Extractie |
|------|--------|-----------|
| `website_crawl` | Hoofddomein URL | Crawler volgt alle interne links |
| `website_sitemap` | Sitemap URL | Alle URLs uit sitemap.xml verwerken |
| `text` | Handmatig getypte tekst | Direct chunken |
| `file` | PDF of CSV upload | pdfplumber (PDF) / pandas (CSV, max 6.000 rijen × 10.000 tekens) |
| `product_feed` | XML feed URL + splitting tag + identifier | Per product één chunk via XML parsing |

---

## PRE-FLIGHT (uitvoeren voor je iets schrijft)

```bash
# 1. Bestaande training workflow — basis voor embedding logica
cat app/services/training_workflow.py | head -100

# 2. Huidige agent_knowledge structuur
psql "$DATABASE_URL" -c "\d agent_knowledge"

# 3. Clients tabel — controleer kolomnamen en PK
psql "$DATABASE_URL" -c "\d clients"

# 4. Bestaat client_knowledge al?
psql "$DATABASE_URL" -c "\d client_knowledge" 2>&1

# 5. Beschikbare Python packages
pip show httpx beautifulsoup4 pdfplumber pandas lxml 2>&1

# 6. BGE-M3 embedding functie locatie
grep -rn "generate_embedding\|bge\|BGE" app/ --include="*.py" | head -10

# 7. Bestaande client detail component
find web_ui/frontend/src -name "Client*.jsx" -o -name "client*.jsx" | head -10
```

Rapporteer alle 7 checks. Stop als `training_workflow.py` niet bestaat of BGE-M3 niet gevonden wordt.

---

## Fase 1 — Database (migration 071)

**Bestand:** `app/migrations/071_client_knowledge.sql`

```sql
-- Client datasources tabel (één per databron die gebruiker aanmaakt)
CREATE TABLE IF NOT EXISTS client_datasources (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                  -- "Algemene voorwaarden", "Website", etc.
    source_type TEXT NOT NULL            -- website_crawl | website_sitemap | text | file | product_feed
        CHECK (source_type IN ('website_crawl', 'website_sitemap', 'text', 'file', 'product_feed')),
    status TEXT DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    -- Website velden
    domain TEXT,                         -- www.asured.nl (voor crawl)
    sitemap_url TEXT,                    -- https://www.asured.nl/sitemap.xml
    -- File velden
    file_name TEXT,                      -- prijslijst-2026.pdf
    file_type TEXT,                      -- pdf | csv
    -- Tekst veld
    raw_text TEXT,                       -- Handmatig ingevoerde tekst
    -- Product feed velden
    feed_url TEXT,                       -- https://www.asured.nl/feed.xml
    feed_splitting_tag TEXT,             -- <item> (XML tag per product)
    feed_identifier_tag TEXT,            -- <g:id> (unieke identifier per product)
    -- Statistieken
    pages_found INTEGER DEFAULT 0,
    pages_processed INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    error_detail TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);

-- Client knowledge tabel (chunks uit alle datasources)
CREATE TABLE IF NOT EXISTS client_knowledge (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    datasource_id BIGINT REFERENCES client_datasources(id) ON DELETE CASCADE,
    source_url TEXT,                     -- Pagina URL of bestandsnaam
    page_title TEXT,                     -- <title> tag of CSV kolomnaam
    chunk_text TEXT NOT NULL,
    embedding vector(1024),              -- BGE-M3 dimensie
    chunk_index INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true,
    added_at TIMESTAMPTZ DEFAULT now()
);

-- HNSW index (sneller dan ivfflat bij grote datasets)
CREATE INDEX IF NOT EXISTS idx_client_knowledge_embedding
    ON client_knowledge USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_client_knowledge_client
    ON client_knowledge(client_id);

CREATE INDEX IF NOT EXISTS idx_client_knowledge_datasource
    ON client_knowledge(datasource_id);
```

**Supabase RPC functie** (uitvoeren in Supabase SQL editor):
```sql
CREATE OR REPLACE FUNCTION match_client_knowledge (
    query_embedding vector(1024),
    match_client_id text,
    match_count int DEFAULT 5,
    similarity_threshold float DEFAULT 0.4
) RETURNS TABLE (
    chunk_text text,
    source_url text,
    page_title text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ck.chunk_text,
        ck.source_url,
        ck.page_title,
        1 - (ck.embedding <=> query_embedding) AS similarity
    FROM client_knowledge ck
    WHERE ck.client_id = match_client_id
      AND ck.is_active = true
      AND 1 - (ck.embedding <=> query_embedding) > similarity_threshold
    ORDER BY ck.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

Migration lokaal uitvoeren:
```bash
psql "$DATABASE_URL" -f app/migrations/071_client_knowledge.sql
```

Verificatie:
```bash
psql "$DATABASE_URL" -c "SELECT table_name FROM information_schema.tables WHERE table_name IN ('client_datasources', 'client_knowledge');"
```

---

## Fase 2 — Backend: Extractie services

### 2A — Website crawler (`app/services/client_crawler.py`)

Twee modi: crawl (volgt links) en sitemap (leest sitemap.xml).

**Klasse structuur:**
```python
class ClientCrawler:
    MAX_PAGES = 100
    CHUNK_SIZE = 3200   # ~800 tokens (1 token ≈ 4 chars)
    CHUNK_OVERLAP = 400

    def __init__(self, client_id: str, datasource_id: int, db_pool): ...

    async def run_crawl(self, domain: str) -> dict:
        """Crawlt alle interne pagina's vanaf het hoofddomein."""

    async def run_sitemap(self, sitemap_url: str) -> dict:
        """Verwerkt alle URLs uit sitemap.xml."""

    async def _process_url(self, url: str) -> dict | None:
        """Scrapet één pagina. Retourneert {title, text} of None."""

    async def _discover_links(self, start_url: str, base_domain: str) -> list[str]:
        """Volgt interne links. Max MAX_PAGES unieke URLs."""

    async def _parse_sitemap(self, sitemap_url: str) -> list[str]:
        """Leest sitemap.xml en retourneert lijst van URLs."""

    def _chunk_text(self, text: str) -> list[str]: ...
    def _normalize_url(self, url: str, base_domain: str) -> str | None: ...
    async def _embed_and_store(self, chunks, source_url, page_title): ...
```

**Kritieke regels:**
- `asyncio.sleep(0.5)` tussen requests
- Timeout: `httpx.AsyncClient(timeout=10.0)`
- User-agent: `"WonderzBot/1.0"`
- Verwijder bestaande chunks voor dezelfde `datasource_id` voor opslag
- Fout op één pagina: log en ga door, stop nooit de hele crawl
- Filter pagina's met < 100 karakters tekst weg
- Gebruik `<main>`, `<article>`, `<section>` bij voorkeur boven `<body>`
- Importeer `generate_embedding` uit `training_workflow.py` — niet kopiëren

### 2B — Tekst processor (`app/services/client_text_processor.py`)

```python
class ClientTextProcessor:
    def __init__(self, client_id: str, datasource_id: int, db_pool): ...

    async def process(self, text: str, source_name: str) -> dict:
        """
        Chunkt handmatig ingevoerde tekst en slaat chunks op.
        Retourneert {chunks_created: int}
        """
```

Geen extractie nodig — tekst is al beschikbaar. Alleen chunken en embedden.

### 2C — File processor (`app/services/client_file_processor.py`)

```python
class ClientFileProcessor:
    CSV_MAX_ROWS = 6_000
    CSV_MAX_CHARS_PER_ROW = 10_000

    def __init__(self, client_id: str, datasource_id: int, db_pool): ...

    async def process_pdf(self, file_bytes: bytes, filename: str) -> dict:
        """
        Extraheert tekst via pdfplumber.
        Per pagina: pdfplumber.open(pdf).pages[i].extract_text()
        Chunkt en embeddt alle tekst.
        """

    async def process_csv(self, file_bytes: bytes, filename: str) -> dict:
        """
        Leest CSV via pandas.
        - Limiet: max CSV_MAX_ROWS rijen (rest afkappen, waarschuwing loggen)
        - Limiet: max CSV_MAX_CHARS_PER_ROW tekens per rij (rij afkappen indien nodig)
        - Elke rij wordt één chunk: "Kolom1: Waarde1 | Kolom2: Waarde2 | ..."
        - Retourneert {chunks_created, rows_processed, rows_skipped, warning?}
        """
```

**Validatie en waarschuwingen:**
- Als CSV > 6.000 rijen: verwerk eerste 6.000, sla `warning` op in `client_datasources.error_detail`: "Bestand bevat X rijen — alleen de eerste 6.000 zijn verwerkt."
- Als een rij > 10.000 tekens: rij afkappen op 10.000, geen fout
- Toon waarschuwing in de UI als `error_detail` gevuld is na `done` status

**Dependencies check:**
```bash
pip show pdfplumber pandas lxml --break-system-packages 2>&1
# Als niet aanwezig:
pip install pdfplumber pandas lxml --break-system-packages
```

### 2D — Product feed processor (`app/services/client_feed_processor.py`)

```python
class ClientFeedProcessor:
    def __init__(self, client_id: str, datasource_id: int, db_pool): ...

    async def process(self, feed_url: str, splitting_tag: str, identifier_tag: str) -> dict:
        """
        1. Download XML feed via httpx
        2. Parse met lxml of xml.etree.ElementTree
        3. Splits op splitting_tag (bijv. <item>)
        4. Per product: bouw chunk tekst van alle sub-elementen
           Formaat: "id: 12345 | title: Productnaam | description: ... | price: 99.95"
        5. Gebruik identifier_tag als source_url (bijv. de g:id waarde)
        6. Embed en sla op in client_knowledge
        Retourneert {products_found, chunks_created}
        """
```

**Chunk formaat per product:**
```
id: 12345
title: Beveiligingscamera Pro
description: Full HD camera met nachtzicht en bewegingsdetectie
price: 149.95
brand: Asured
availability: in stock
```

**Kritieke regels:**
- Max 10.000 producten per feed (daarna stoppen, waarschuwing loggen)
- Lege velden weglaten uit de chunk tekst
- Bij XML parse fout: log error_detail, status → failed

---

## Fase 3 — Backend: API endpoints

**Bestand:** `app/routes/clients.py` (toevoegen aan bestaande file)

```
# Datasource CRUD
POST   /api/clients/{client_id}/datasources
       Body: {name, source_type, domain?, sitemap_url?, raw_text?}
       Response: {datasource_id, status: "pending"}

GET    /api/clients/{client_id}/datasources
       Response: [{id, name, source_type, status, chunks_created, finished_at}]

DELETE /api/clients/{client_id}/datasources/{datasource_id}
       Verwijdert datasource + alle bijbehorende chunks

# Verwerking starten
POST   /api/clients/{client_id}/datasources/{datasource_id}/process
       Start verwerking als background task (crawl, sitemap, tekst)
       Response: {status: "processing"}

# File upload (PDF of CSV)
POST   /api/clients/{client_id}/datasources/{datasource_id}/upload
       Multipart form: file (pdf of csv)
       Detecteert type automatisch op extensie
       Start verwerking direct als background task
       Response: {status: "processing", file_name, warning?}

# Product feed starten (URL al opgeslagen bij aanmaken datasource)
POST   /api/clients/{client_id}/datasources/{datasource_id}/process
       Werkt ook voor product_feed type — gebruikt feed_url, splitting_tag, identifier_tag
       Response: {status: "processing"}

# Status polling
GET    /api/clients/{client_id}/datasources/{datasource_id}/status
       Response: {status, pages_found, pages_processed, chunks_created, error_detail, percent}

# Knowledge overzicht
GET    /api/clients/{client_id}/knowledge
       Response: {
           chunks_total,
           datasources: [{name, type, chunks, last_updated}]
       }
```

**Implementatiedetails:**
- `POST /process` en `POST /upload` starten background task via `asyncio` — retourneer direct
- Background task update `client_datasources` na elke pagina/chunk batch
- Auth: gebruik bestaande `require_auth` dependency
- File upload: sla bestand tijdelijk op in `/tmp/` — verwijder na verwerking

---

## Fase 4 — CEO context injectie

**Bestand:** `app/services/job_pipeline.py` of `app/agents/ceo_agent.py`

### Mention detectie
```python
import re

def extract_client_mention(job_post: str) -> str | None:
    match = re.search(r'@([a-zA-Z0-9_-]+)', job_post)
    return match.group(1).lower() if match else None
```

### Client opzoeken
```sql
SELECT id, name, slug FROM clients
WHERE LOWER(slug) = $1 OR LOWER(name) = $1
LIMIT 1;
```

### Context retrieval
```sql
SELECT chunk_text, source_url, page_title,
       1 - (embedding <=> $1) AS similarity
FROM client_knowledge
WHERE client_id = $2
  AND is_active = true
  AND 1 - (embedding <=> $1) > 0.4
ORDER BY embedding <=> $1
LIMIT 5;
```

Als similarity_threshold niet gehaald wordt (geen chunks boven 0.4): injecteer geen context, geef CEO een notitie mee dat er geen relevante kennis beschikbaar is voor deze client.

### Context injectie in CEO prompt
```python
CLIENT_CONTEXT_TEMPLATE = """
## [CONTEXT] Client: {client_name}

De volgende informatie is afkomstig van de kennisbronnen van {client_name}.
Gebruik deze informatie als primaire bron. Verzin geen feiten die hier niet instaan.
Als de context onvoldoende is, geef dit aan in je plan.

{chunks}

---
## [TAAK]
"""

# chunks formaat:
# Bron (asured.nl/diensten): "Asured biedt 24/7 netwerkmonitoring..."
# Bron (Algemene voorwaarden.pdf): "Artikel 3: Betalingstermijn is 30 dagen..."
```

---

## Fase 5 — Frontend

**Bestand:** bestaande client detail pagina (zoek met):
```bash
find web_ui/frontend/src -name "Client*.jsx" -o -name "client*.jsx" | head -10
```

Voeg een **"Kennisbronnen"** sectie/tab toe aan de client detail pagina.

### UI structuur

**Overzicht (lijst van datasources):**
```
┌─────────────────────────────────────────────────────────┐
│  Kennisbronnen                          [+ Bron toevoegen]│
│                                                          │
│  🌐 Website          ✅ 312 chunks  asured.nl    [⋮]    │
│  📄 Algemene voorwaarden  ✅ 28 chunks  PDF       [⋮]    │
│  📊 Prijslijst 2026  🔄 Bezig...                  [⋮]    │
│  📝 Tone of voice    ✅ 12 chunks  Tekst          [⋮]    │
└─────────────────────────────────────────────────────────┘
```

**"Bron toevoegen" modal — stap 1: naam + type kiezen:**
```
┌─────────────────────────────────────────┐
│  Nieuwe kennisbron                      │
│                                         │
│  Naam: [__________________________]     │
│                                         │
│  ○ 🌐 Website crawlen                   │
│     Zoekt alle pagina's op het domein   │
│                                         │
│  ○ 🗺️  Sitemap indienen                 │
│     Verwerkt alle URLs uit sitemap.xml  │
│                                         │
│  ○ 📄 Bestand uploaden (PDF of CSV)     │
│                                         │
│  ○ 📝 Tekst invoeren                    │
│                                         │
│                    [Annuleren] [Volgende]│
└─────────────────────────────────────────┘
```

**Stap 2a — Website crawlen:**
```
URL: [https://www.asured.nl    ] [Pagina's zoeken]
```

**Stap 2b — Sitemap:**
```
Sitemap URL: [https://www.asured.nl/sitemap.xml] [Toevoegen]
```

**Stap 2c — Bestand:**
```
[Sleep PDF of CSV hier of klik om te uploaden]
Max 10MB · PDF of CSV
```

**Stap 2d — Tekst:**
```
[Grote textarea voor vrije tekst invoer]
```

**Stap 2e — Product feed:**
```
Feed URL:              [https://www.asured.nl/feed.xml]
Splitting tag:         [<item>              ]  bv. <item>
Unieke identificator:  [<g:id>              ]  bv. <g:id>
```

**Tijdens verwerking (polling elke 3s):**
```
🔄 Website — Bezig...
████████░░░░  24 / 48 pagina's · 156 chunks aangemaakt
```

**Technische eisen:**
- Polling via `setInterval` elke 3000ms, stop bij `done` of `failed`
- Bij `failed`: toon `error_detail`
- `[⋮]` menu per bron: Opnieuw verwerken / Verwijderen
- Gebruik bestaande design tokens van het platform

---

## Fase 6 — Verificatie

```bash
# 1. Tabellen aanwezig (lokaal)
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM client_datasources;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM client_knowledge;"

# 2. Test website crawl (Shelley — vereist token op server)
curl -X POST http://localhost:8090/api/clients/<client_id>/datasources \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "Website Asured", "source_type": "website_crawl", "domain": "www.asured.nl"}'

# Daarna process starten (Shelley)
curl -X POST http://localhost:8090/api/clients/<client_id>/datasources/<ds_id>/process \
  -H "Authorization: Bearer <token>"

# 3. Status pollen (Shelley)
curl http://localhost:8090/api/clients/<client_id>/datasources/<ds_id>/status \
  -H "Authorization: Bearer <token>"

# 4. Chunks in DB na done (lokaal)
psql "$DATABASE_URL" -c "
SELECT source_url, COUNT(*) as chunks
FROM client_knowledge
WHERE client_id = '<client_id>'
GROUP BY source_url
ORDER BY chunks DESC LIMIT 10;
"

# 5. CEO context test (Shelley) — maak een job aan met @asured in de tekst
# Verwacht: CEO prompt bevat [CONTEXT] Client: Asured sectie
```

**Acceptatiecriteria:**
- [ ] Datasource aanmaken werkt voor alle 5 typen
- [ ] Website crawl verwerkt pagina's, status pollt correct
- [ ] Sitemap verwerkt alle URLs uit sitemap.xml
- [ ] PDF upload extraheert tekst correct
- [ ] CSV upload: max 6.000 rijen, max 10.000 tekens per rij, waarschuwing bij overschrijding
- [ ] Product feed: splits op splitting_tag, één chunk per product
- [ ] Chunks aanwezig in `client_knowledge` na verwerking
- [ ] CEO injecteert context bij `@asured` mention
- [ ] Similarity < 0.4: geen context, CEO krijgt notitie
- [ ] UI toont voortgang tijdens verwerking
- [ ] Waarschuwing zichtbaar in UI als CSV limieten overschreden zijn

---

## Wat je NIET doet

- Geen JavaScript rendering (geen Playwright) — alleen statische HTML
- Geen `training_workflow.py` aanpassen — alleen `generate_embedding` importeren
- Geen chunks van externe domeinen opslaan
- Geen bestand permanent opslaan — alleen `/tmp/`, verwijder na verwerking
- Geen nieuwe sidebar routes of pagina's — sectie op bestaande client detail pagina

---

## Commit volgorde

```
feat: client_datasources + client_knowledge tables (migration 071)
feat: client crawler service (crawl + sitemap modes)
feat: client text + file processor (PDF, CSV met limieten)
feat: client product feed processor (XML splitting)
feat: client knowledge API endpoints
feat: CEO client context injection on @mention
feat: client detail UI - kennisbronnen sectie (5 brontypen)
```

---

*Stack: FastAPI + asyncpg + BGE-M3 (lokaal) + pgvector HNSW*
*Referentie: app/services/training_workflow.py (embedding logica)*
*Spec: Wonderz Platform Overzicht v2, maart 2026*
