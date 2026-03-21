# Google Integrations — Taakdocument
**Datum:** 20 maart 2026 | **Status:** Open | **Prioriteit:** Gefaseerd

---

## Doel

Uitbreiden van de Wonderz-Agentics platform met Google API-integraties die agents voorzien van rijke, realtime data. Elke integratie heeft een concreet doel binnen de agent-architectuur: SEO-agent, GTM Specialist, QA Reviewer, of clientrapporten.

---

## Fase 1 — Directe waarde, lage drempel

### 1. PageSpeed Insights API
- **Wat:** Core Web Vitals + technische SEO-data per URL
- **Auth:** Geen OAuth, alleen API key
- **Agent-gebruik:** SEO-agent (input voor technische audit), ClientDashboard (PDF rapport)
- **Scope:** `GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile`
- **Output:** LCP, FID, CLS, TTFB, performance score (0-100)
- **Status:** [ ] Te implementeren

### 2. Chrome UX Report (CrUX) API
- **Wat:** Real-world laadtijddata van echte Chrome-gebruikers, historische trends per domein
- **Auth:** Geen OAuth, alleen API key
- **Agent-gebruik:** Complementair aan PageSpeed, historische context voor SEO-agent
- **Scope:** `POST https://chromeuxreport.googleapis.com/v1/records:queryRecord`
- **Output:** p75 metrics per URL: LCP, FID, CLS, INP, TTFB — plus historische distributies
- **Status:** [ ] Te implementeren

---

## Fase 2 — Client-specifieke data

### 3. Business Profile API (Google My Business)
- **Wat:** Reviews, zoektermen via Maps, Q&A, postprestaties per locatie
- **Auth:** OAuth 2.0 (per klant koppelen)
- **Agent-gebruik:** GTM Specialist (local SEO-strategie), SEO-agent (review-analyse)
- **Scope:**
  - `GET /v4/accounts/{accountId}/locations` — locaties ophalen
  - `GET /v4/accounts/{accountId}/locations/{locationId}/reviews` — reviews
  - `GET /v4/accounts/{accountId}/locations/{locationId}/insights` — zoektermen, acties
- **Output:** Reviewscore, reviewteksten, hoe klanten zoeken (direct/discovery/branded), acties (bellen, routebeschrijving, website)
- **Status:** [ ] Te implementeren

### 4. YouTube Data API v3 + YouTube Analytics API
- **Wat:** Channeldata, videometrics, kijkgedrag
- **Auth:** OAuth 2.0 (per klant koppelen)
- **Agent-gebruik:** Content-agent (videostrategie), GTM Specialist (channelanalyse)
- **Scope:**
  - YouTube Data API: channels, videos, playlists, search
  - YouTube Analytics API: views, watchTime, subscribers, traffic sources
- **Output:** Views per video, kijkduur, clickthrough rate, subscriber groei, top traffic sources
- **Status:** [ ] Te implementeren

---

## Fase 3 — Verrijking en kwaliteitscontrole

### 5. Natural Language API
- **Wat:** Sentimentanalyse, entity-extractie, inhoudsclassificatie
- **Auth:** API key (geen OAuth)
- **Agent-gebruik:** QA Reviewer (objectieve beoordeling gegenereerde copy op toon, entiteiten, relevantie)
- **Scope:**
  - `analyzeSentiment` — toon per zin/document
  - `analyzeEntities` — welke entiteiten worden benoemd
  - `classifyText` — inhoudsclassificatie
- **Output:** Sentiment score + magnitude, entiteiten met salience score, contentkategorieën
- **Status:** [ ] Te implementeren

### 6. Google Merchant Center API (Shopping Content API)
- **Wat:** Productfeeddata, approve/reject statussen, prijsvergelijking
- **Auth:** OAuth 2.0 (per klant koppelen)
- **Agent-gebruik:** E-commerce klanten via Shopify-adapter
- **Scope:**
  - `products.list` — productfeed ophalen
  - `productstatuses.list` — approve/disapprove statussen
  - `accounts.get` — accountstatus en issues
- **Output:** Productstatus per item, disapproval-redenen, feed-kwaliteitsscore
- **Status:** [ ] Te implementeren

### 7. Indexing API
- **Wat:** URL's aanmelden voor Google-indexering
- **Auth:** Service Account (geen OAuth per klant, wel verificatie eigenaarschap)
- **Agent-gebruik:** SEO-agent, na publicatie via WordPress/Shopify adapter
- **Scope:** `POST https://indexing.googleapis.com/v3/urlNotifications:publish`
- **Output:** Bevestiging indexeringsverzoek + timestamp
- **Vereiste:** Search Console eigenaarschap geverifieerd per domein
- **Status:** [ ] Te implementeren

---

## Fase 4 — Later / laag prioriteit

### 8. Knowledge Graph API
- **Wat:** Gestructureerde entiteitsdata (wat Google weet over merk/persoon/bedrijf)
- **Auth:** API key
- **Agent-gebruik:** Contentverrijking, merkentiteit-verificatie
- **Status:** [ ] Backlog

### 9. Google Translate API
- **Wat:** Meertalige content genereren
- **Auth:** API key
- **Kosten:** Betaald per karakter (~$20 per 1M tekens)
- **Status:** [ ] Backlog — pas relevant als meertalige klanten actief zijn

### 10. Google Sheets API
- **Wat:** Briefs en contentkalenders inlezen vanuit Sheets
- **Auth:** OAuth 2.0
- **Noot:** Lage prioriteit, Wonderz heeft robuustere datalaag. Alleen relevant voor klanten die briefs via Sheets aanleveren.
- **Status:** [ ] Backlog

---

## Technische architectuur

Alle integraties volgen hetzelfde patroon als de bestaande GA4/GSC/Ads adapters:

```
app/integrations/
  google_pagespeed.py       # Fase 1
  google_crux.py            # Fase 1
  google_business_profile.py # Fase 2
  google_youtube.py         # Fase 2
  google_natural_language.py # Fase 3
  google_merchant_center.py  # Fase 3
  google_indexing.py         # Fase 3
```

**Per adapter:**
- Eigen Python module in `app/integrations/`
- API key of OAuth token via `systemd override` (nooit hardcoded)
- Wrapper functie die ruwe API-response omzet naar gestandaardiseerd dict
- Foutafhandeling: timeout, quota exceeded, auth errors
- Logging via `journalctl`

**OAuth flow (voor Business Profile, YouTube, Merchant Center):**
- Per-klant koppeling, zelfde OAuth flow als huidige GA4/Ads
- Token opgeslagen in `client_integrations` tabel per `client_id`
- Refresh token logic via bestaande Google OAuth helper

---

## Implementatievolgorde (aanbevolen)

| # | API | Fase | Auth | Drempel | Impact |
|---|-----|------|------|---------|--------|
| 1 | PageSpeed Insights | 1 | API key | Laag | Hoog |
| 2 | CrUX | 1 | API key | Laag | Middel |
| 3 | Natural Language | 3 | API key | Laag | Hoog (QA) |
| 4 | Indexing API | 3 | Service Account | Middel | Hoog (SEO) |
| 5 | Business Profile | 2 | OAuth | Middel | Hoog (lokaal) |
| 6 | YouTube | 2 | OAuth | Middel | Middel |
| 7 | Merchant Center | 3 | OAuth | Hoog | Hoog (e-com) |
| 8 | Knowledge Graph | 4 | API key | Laag | Laag |
| 9 | Translate | 4 | API key | Laag | Laag |
| 10 | Sheets | 4 | OAuth | Middel | Laag |

---

## Acceptatiecriteria (per fase)

**Fase 1 klaar als:**
- [ ] PageSpeed data opvraagbaar per client domain
- [ ] CrUX historische data beschikbaar per domain
- [ ] Beide outputs zichtbaar in ClientDashboard en beschikbaar als agent-context

**Fase 2 klaar als:**
- [ ] Business Profile reviews + insights ophaalbaar per gekoppelde klant
- [ ] YouTube metrics beschikbaar per gekoppeld kanaal
- [ ] Data flows naar GTM Specialist als job-context

**Fase 3 klaar als:**
- [ ] Natural Language API aangeroepen door QA Reviewer bij elke copy-review
- [ ] Indexing API aangeroepen door SEO-agent na publicatie
- [ ] Merchant Center feed-kwaliteit zichtbaar in ClientDashboard

---

## Open vragen

- [ ] Welke klanten hebben een Google Business Profile? Inventariseren voor prioritering Fase 2
- [ ] Natural Language API: per job aanroepen of alleen on-demand?
- [ ] Indexing API: automatisch na publicatie of handmatig triggeren via UI?
- [ ] Merchant Center: aparte tab in ClientDashboard of inline in bestaande metrics?
