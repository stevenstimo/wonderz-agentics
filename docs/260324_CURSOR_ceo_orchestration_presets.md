# 260324_CURSOR_ceo_orchestration_presets

## Verplichte git-regels — lees dit eerst

- Nooit `git restore`, `git checkout --force`, `git reset` of `git clean` uitvoeren
- Bij elke git-operatie eerst `git status` rapporteren en wachten op bevestiging
- Alleen specifieke bestanden stagen, nooit `git add -A`

---

## Context

Je werkt aan **Wonderz-Agentics**, een multi-agent marketing platform op FastAPI + asyncpg.
Lokale PostgreSQL: `postgresql://wonderz:wonderz123@localhost:5432/wonderz`
Laatste migratie: `046_newbie_library.sql`

De CEO-orchestrator is **Donna Paulsen** (`agent:personal-assistant:donna`).
De COO is **Mr. Klein** (`agent:ceo:mr-klein`).

Dit document implementeert drie samenhangende onderdelen in volgorde. Werk fase voor fase af. Stop na elke fase en rapporteer wat gebouwd is voordat je verdergaat.

---

## Pre-flight checklist

Voer dit uit vóór je begint. Als een check faalt: stop en meld het.
```sql
-- 1. hired_agents aanwezig
SELECT COUNT(*) FROM hired_agents;

-- 2. Donna aanwezig
SELECT agent_id, role FROM hired_agents WHERE agent_id = 'agent:personal-assistant:donna';

-- 3. Mr. Klein aanwezig
SELECT agent_id, role FROM hired_agents WHERE agent_id = 'agent:ceo:mr-klein';

-- 4. jobs tabel aanwezig
SELECT COUNT(*) FROM jobs LIMIT 1;

-- 5. Laatste migratie
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
```

---

## Fase 1 — Database: job_type_presets + preset_bookings

### Wat je bouwt

Migratie `047_job_type_presets.sql` met twee nieuwe tabellen en seed-data voor 8 presets.

### Bestand: `migrations/047_job_type_presets.sql`

CREATE TABLE IF NOT EXISTS job_type_presets (
    preset_id       TEXT PRIMARY KEY,
    job_type        TEXT NOT NULL,
    description     TEXT NOT NULL,
    trigger_hint    TEXT,
    agent_slots     JSONB NOT NULL DEFAULT '[]',
    kpi_targets     JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN DEFAULT true,
    usage_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS preset_bookings (
    booking_id      BIGSERIAL PRIMARY KEY,
    job_id          UUID REFERENCES jobs(id) ON DELETE CASCADE,
    preset_id       TEXT REFERENCES job_type_presets(preset_id),
    agent_id        TEXT REFERENCES hired_agents(agent_id),
    slot_role       TEXT NOT NULL,
    deviation       BOOLEAN DEFAULT false,
    deviation_reason TEXT,
    booked_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_presets_active ON job_type_presets(is_active);
CREATE INDEX IF NOT EXISTS idx_preset_bookings_job ON preset_bookings(job_id);
CREATE INDEX IF NOT EXISTS idx_preset_bookings_preset ON preset_bookings(preset_id);

INSERT INTO job_type_presets (preset_id, job_type, description, trigger_hint, agent_slots, kpi_targets) VALUES
('seo-content-campaign','SEO Content Campagne','Keyword-gedreven content die autoriteit opbouwt','seo, blog, content, artikel, pillar page, zoekwoorden, organic','[{"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},{"slot":"strategist","role":"SEO Content Strategist","agent_type":"worker","persona":"Mike Ross","required":true},{"slot":"copywriter","role":"Copywriter","agent_type":"worker","persona":"Forrest Gump","required":true},{"slot":"reviewer","role":"SEO Reviewer / QA","agent_type":"talent","persona":"Alan Turing","required":true},{"slot":"distribution","role":"Distribution Strategist","agent_type":"worker","persona":"Keanu Reeves","required":false}]','{"kpis":["Organisch verkeer +X% binnen 90 dagen","Top-10 voor target keywords"],"outputs":["Pillar page","Cluster artikelen","Distributiebriefing"]}'),
('paid-ads-launch','Paid Ads Launch','Van briefing naar live campagne met gevalideerde creatives','ads, campagne, advertentie, media, facebook, google ads, budget, roas','[{"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},{"slot":"scriptwriter","role":"Scriptwriter & Hook Specialist","agent_type":"worker","persona":"Ferris Bueller","required":true},{"slot":"media_buyer","role":"Media Buyer","agent_type":"worker","persona":"Winston Wolf","required":true},{"slot":"tracking","role":"Tracking Architect","agent_type":"worker","persona":"Q","required":true},{"slot":"reviewer","role":"QA Reviewer","agent_type":"talent","persona":"Patrick Bateman","required":true}]','{"kpis":["ROAS target behaald binnen 14 dagen","CPM/CPC binnen benchmarks"],"outputs":["Campagnestructuur","Gevalideerde creatives","Tracking rapport"]}'),
('ecommerce-launch','E-commerce Product Launch','Van productinformatie naar geoptimaliseerde pagina','product launch, webshop, productpagina, shopify, wordpress, collectie','[{"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},{"slot":"coo","role":"COO Coordinator","agent_type":"coo","persona":"Mr. Klein","required":true},{"slot":"merchandising","role":"Merchandising & Pricing","agent_type":"worker","persona":"Man with No Name","required":true},{"slot":"copywriter","role":"Copywriter","agent_type":"worker","persona":"Forrest Gump","required":true},{"slot":"seo","role":"SEO Specialist","agent_type":"worker","persona":"Donnie Darko","required":true},{"slot":"reviewer","role":"QA Reviewer","agent_type":"talent","persona":"Alan Turing","required":true}]','{"kpis":["SEO-score: APPROVED","Conversion rate boven gemiddelde","Time-to-live <48u"],"outputs":["Productpagina","SEO meta-teksten","Pricing rapport"]}'),
('retention-lifecycle','Retention & Lifecycle Campagne','Klanten activeren voor herhaalaankoop en hogere LTV','retention, lifecycle, churn, loyalty, email flow, herhaalaankoop, ltv','[{"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},{"slot":"insights","role":"Customer Insights Specialist","agent_type":"worker","persona":"Jeffrey Beaumont","required":true},{"slot":"copywriter","role":"Copywriter","agent_type":"worker","persona":"Forrest Gump","required":true},{"slot":"format","role":"Format Developer","agent_type":"worker","persona":"Keanu Reeves","required":false},{"slot":"reviewer","role":"QA Reviewer","agent_type":"talent","persona":"Data","required":true}]','{"kpis":["Repeat purchase rate +X%","LTV stijging binnen 60 dagen"],"outputs":["Win-back flow","Loyalty communicatie","Insights rapport"]}'),
('brand-narrative','Brand Narrative & Strategie','Het merkverhaal definieren dat alle communicatie verankert','merk, brand, positionering, narratief, strategie, tone of voice, brand voice','[{"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},{"slot":"coo","role":"COO Coordinator","agent_type":"coo","persona":"Mr. Klein","required":true},{"slot":"narrative","role":"Narrative Designer","agent_type":"worker","persona":"Jeanne d Arc","required":true},{"slot":"copywriter","role":"Copywriter","agent_type":"worker","persona":"Forrest Gump","required":true},{"slot":"reviewer","role":"QA Reviewer","agent_type":"talent","persona":"Hannibal Lecter","required":true}]','{"kpis":["Brand voice goedgekeurd","Narratief consistent over touchpoints"],"outputs":["Brand story","Tone of voice guide","GTM deck"]}'),
('data-infra-setup','Data & Tracking Infrastructuur','Een schone meetstructuur als fundament voor alle AI-beslissingen','tracking, data, analytics, ga4, gtm, server-side, cdp, dashboard, meting','[{"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},{"slot":"coo","role":"COO Coordinator","agent_type":"coo","persona":"Mr. Klein","required":true},{"slot":"tracking","role":"Tracking Architect","agent_type":"worker","persona":"Agent K","required":true},{"slot":"data_eng","role":"Data Engineer","agent_type":"worker","persona":"Tony Stark","required":true},{"slot":"compliance","role":"Privacy & Compliance","agent_type":"worker","persona":"Agent Smith","required":true},{"slot":"reviewer","role":"QA Reviewer","agent_type":"talent","persona":"Alan Turing","required":true}]','{"kpis":[">95% event accuracy","AVG compliance: APPROVED"],"outputs":["Server-side tracking","Verificatie rapport","BI dashboard"]}'),
('data-query','Data Analyse & Rapportage','Dataverzoeken en analyses op basis van bestaande data','data, analyse, rapport, cijfers, statistieken, inzicht, keyword research, zoekvolume, metrics, performance, resultaten','[{"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},{"slot":"coo","role":"COO Coordinator","agent_type":"coo","persona":"Mr. Klein","required":true},{"slot":"analyst","role":"Data Analyst","agent_type":"worker","persona":"Mike Ross","required":true},{"slot":"reviewer","role":"QA Reviewer","agent_type":"talent","persona":"Alan Turing","required":false}]','{"kpis":["Correcte data-output zonder hallucinaties","Bronvermelding bij elke claim"],"outputs":["Data rapport","Gestructureerde tabel of export"]}'),
('seo-keyword-research','SEO Keyword Research','Keyword analyse via de SEO tool gerouteerd via COO','keyword, zoekwoorden, keyword research, zoekvolume, concurrentie, serp, search intent, diamond pigs, keyword plan','[{"slot":"ceo","role":"CEO Orchestrator","agent_type":"ceo","persona":"Donna Paulsen","required":true},{"slot":"coo","role":"COO Coordinator","agent_type":"coo","persona":"Mr. Klein","required":true},{"slot":"seo","role":"SEO Specialist","agent_type":"worker","persona":"Mike Ross","required":true},{"slot":"reviewer","role":"SEO Reviewer / QA","agent_type":"talent","persona":"Alan Turing","required":false}]','{"kpis":["Keyword plan goedgekeurd door QA","Zoekintentie correct geclassificeerd"],"outputs":["Keyword plan met zoekvolume en intent","Prioriteitenlijst voor content"]}')
ON CONFLICT (preset_id) DO NOTHING;

### Verificatie na fase 1

SELECT preset_id, job_type, jsonb_array_length(agent_slots) AS slots FROM job_type_presets ORDER BY preset_id;

Verwacht: 8 rijen. Stop hier en rapporteer de output. Wacht op bevestiging voor fase 2.

---

## Fase 2 — app/orchestration/ceo_intent.py

Maak nieuw bestand `app/orchestration/ceo_intent.py`:

- `detect_job_type(db, job_description)`: matcht job-beschrijving op trigger_hint keywords, retourneert preset_id of None
- `check_resources(db, preset_id)`: controleert of required agents actief zijn, retourneert dict met ready/covered/missing/message
- `build_execution_plan(db, job_id, preset_id, resource_report)`: bouwt ExecutionPlan, alleen aanroepen als ready=True

Principe hardcoded als comment bovenaan: "liever een helder nee dan slechte output."

CEO-agent hardcoded op `agent:personal-assistant:donna`.
COO-agent hardcoded op `agent:ceo:mr-klein`.

Schrijf daarna `app/tests/test_ceo_intent.py` met twee tests:
1. detect_job_type("schrijf een blog artikel over SEO") == "seo-content-campaign"
2. check_resources("seo-content-campaign") retourneert dict met "ready" en "message"

Voer de tests uit en rapporteer de output. Stop hier. Wacht op bevestiging voor fase 3.

---

## Fase 3 — CEO intake koppeling + SEO routing

Zoek de job-intake functie in nexus_pipeline.py of ceo_agent.py. Voeg toe na ontvangen job-beschrijving, voor het ExecutionPlan:

1. Roep detect_job_type aan
2. Als preset gevonden: roep check_resources aan
3. Als not ready: update job status naar BLOCKED met resource_report["message"], return BLOCKED response
4. Als geen preset gevonden: update job status naar BLOCKED met "Onbekend jobtype. Omschrijf de opdracht specifieker of hire de juiste agent."
5. Als ready: ga verder met build_execution_plan en de bestaande pipeline

Zoek het SEO-endpoint (/api/seo/...). Voeg guard toe: alleen aanroepbaar als initiated_by in ("ceo", "coo"), anders HTTP 403.

Rapporteer welke bestanden gewijzigd zijn. Stop. Wacht op bevestiging voor commits.

---

## Commits (alleen na expliciete bevestiging van mij)

git add migrations/047_job_type_presets.sql app/orchestration/ceo_intent.py app/tests/test_ceo_intent.py
git commit -m "feat: job_type_presets seed and CEO intent detection with resource check"

git add [gewijzigd intake bestand] [gewijzigd SEO bestand]
git commit -m "feat: CEO blocks job with BLOCKED status when resources missing"

## Wat je NIET doet

- Geen git add -A
- Geen git restore / checkout --force / reset / clean zonder mijn bevestiging
- Niet verder dan fase 1 totdat verificatie 8 rijen toont
- Geen bestaande job-flow breken
