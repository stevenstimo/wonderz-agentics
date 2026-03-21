# CURSOR PROMPT — Google Integrations: Volledige Architectuur
**Datum:** 20 maart 2026 | **Repo:** wonderz-agentics | **Regels:** @backend-architect @frontend-developer

---

## Doel

Bouw de volledige infrastructuur voor alle 10 Google API-integraties in één implementatieronde. Elke integratie wordt als disabled module gebouwd. Activeren gebeurt later per integratie via één env-var in het systemd override bestand — zonder codewijziging.

**Principe:** Alles klaarstaat. Niets gaat live totdat de key/token wordt gezet.

---

## Wat je NIET doet

- Geen hardcoded API keys, tokens of credentials in code
- Geen `.env` aanpassen — alleen systemd override (`/etc/systemd/system/wonderz-backend.service.d/override.conf`)
- Geen bestaande integrations aanpassen of verwijderen (GA4, GSC, Ads, Meta blijven onaangeroerd)
- Geen routes aanmaken die al bestaan
- Geen `git add -A` — alleen specifieke bestanden stagen
- Geen Vercel of Fly.io deployment stappen

---

## Pre-flight checks (uitvoeren vóór eerste codewijziging)

```bash
# 1. Controleer bestaande integrations map
ls app/integrations/

# 2. Controleer bestaande client_integrations tabel
psql $DATABASE_URL -c "\d client_integrations"

# 3. Controleer bestaande OAuth helper
grep -n "def refresh_token\|def get_oauth_token\|def google_oauth" app/integrations/*.py | head -20

# 4. Controleer bestaande env vars patroon in backend
grep -n "GOOGLE_\|os.getenv" app/integrations/google_analytics.py | head -20

# 5. Backend gezond
curl -s http://localhost:8090/api/health | python3 -m json.tool
```

Rapporteer alle uitkomsten vóór je verder gaat.

---

## Repo-specifieke afspraken (wonderz-agentics)

- **Router-pad:** nieuwe endpoints horen in **`app/routes/`**, niet in `app/routers/`. Registreer in [`app/main.py`](../app/main.py) met `from app.routes import google_integrations` en `app.include_router(google_integrations.router)` (zelfde patroon als `integrations`, `clients`, …).
- **Migratienummer:** gebruik **`app/migrations/083_google_integrations.sql`**. Het nummer `050_` is al bezet door [`050_clients_table.sql`](../app/migrations/050_clients_table.sql).
- **Frontend:** [`useAuthReady`](../web_ui/frontend/src/useAuthReady.js) retourneert `{ authReady, session }`, geen `token`. Gebruik [`apiFetch`](../web_ui/frontend/src/apiClient.js) uit `apiClient.js` (zet automatisch `Authorization: Bearer` via Supabase-session); geen handmatige `fetch` + Bearer.
- **`client_integrations`-index:** in dit schema zijn **`user_id`** en **`client_slug`** leidend (geen `client_id` in de basis-migratie). De migratie-SQL hieronder gebruikt daarom een index op `(user_id, client_slug, provider)`.

### Route-conflictcheck (bestaand vs nieuw)

[`app/routes/integrations.py`](../app/routes/integrations.py) heeft prefix **`/api/integrations`**. Deze paden bestaan al en mogen **niet** dubbel gedefinieerd worden:

| Methode | Volledig pad |
|---------|----------------|
| `POST` | `/api/integrations/google/auth-url` |
| `GET` | `/api/integrations/google/callback` |
| `POST` | `/api/integrations/google/refresh` |

De **nieuwe** router krijgt prefix **`/api/integrations/google`** met o.a. `GET /status`, `POST /pagespeed`, `POST /crux`, enz. Dat levert `/api/integrations/google/status`, `/api/integrations/google/pagespeed`, … — **geen overlap** met de drie rijen hierboven (let op: `/google/callback` is alleen de bestaande OAuth-callback; het nieuwe bestand definieert geen tweede `/callback`).

---

## Architectuur

### Feature Flag systeem

Elke integratie heeft één env-var die bepaalt of hij actief is. Als de var niet gezet is of leeg is, retourneert de adapter altijd `{"enabled": false, "data": None}` zonder fout.

**Patroon per integratie:**

```python
import os

ENABLED = bool(os.getenv("GOOGLE_PAGESPEED_API_KEY"))

async def fetch(...):
    if not ENABLED:
        return {"enabled": False, "data": None}
    # echte implementatie
```

**Env vars overzicht (voor systemd override — nog NIET zetten):**

```
# API-key integraties (geen OAuth)
GOOGLE_PAGESPEED_API_KEY=
GOOGLE_CRUX_API_KEY=
GOOGLE_NL_API_KEY=
GOOGLE_KNOWLEDGE_GRAPH_API_KEY=
GOOGLE_TRANSLATE_API_KEY=

# Service Account (Indexing API)
GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON=

# OAuth integraties (per klant via DB — geen env var nodig voor activatie)
# Business Profile, YouTube, Merchant Center, Sheets worden geactiveerd
# zodra een klant OAuth koppelt via de Integrations UI
```

---

## Database migratie

Maak **`app/migrations/083_google_integrations.sql`** (niet `050_`: die filename bestaat al).

```sql
-- Uitbreiden client_integrations tabel met nieuwe provider-types
-- Voeg toe als de kolom nog niet bestaat

ALTER TABLE client_integrations
  ADD COLUMN IF NOT EXISTS provider TEXT,
  ADD COLUMN IF NOT EXISTS scopes TEXT[],
  ADD COLUMN IF NOT EXISTS extra_data JSONB DEFAULT '{}';

-- Index voor snelle provider-lookup (user_id + client_slug: wonderz-schema)
CREATE INDEX IF NOT EXISTS idx_client_integrations_provider
  ON client_integrations(user_id, client_slug, provider);

-- Tabel voor API-key integraties op platform-niveau (niet per klant)
CREATE TABLE IF NOT EXISTS platform_integrations (
  id            BIGSERIAL PRIMARY KEY,
  provider      TEXT NOT NULL UNIQUE,   -- 'pagespeed', 'crux', 'natural_language', etc.
  is_enabled    BOOLEAN DEFAULT false,
  last_checked  TIMESTAMPTZ,
  error_message TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Seed alle bekende providers (disabled by default)
INSERT INTO platform_integrations (provider, is_enabled) VALUES
  ('pagespeed', false),
  ('crux', false),
  ('natural_language', false),
  ('indexing', false),
  ('knowledge_graph', false),
  ('translate', false)
ON CONFLICT (provider) DO NOTHING;

-- Client-level OAuth providers
INSERT INTO platform_integrations (provider, is_enabled) VALUES
  ('business_profile', false),
  ('youtube', false),
  ('merchant_center', false),
  ('sheets', false)
ON CONFLICT (provider) DO NOTHING;
```

---

## Backend — adapter modules

Maak de volgende bestanden aan in `app/integrations/`. Elk bestand is volledig zelfstandig en doet niets als de env var ontbreekt.

---

### `app/integrations/google_pagespeed.py`

```python
"""
Google PageSpeed Insights API adapter.
Geeft Core Web Vitals + performance score per URL.
Activeren: zet GOOGLE_PAGESPEED_API_KEY in systemd override.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_PAGESPEED_API_KEY", "")
BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
ENABLED = bool(API_KEY)


async def fetch_pagespeed(url: str, strategy: str = "mobile") -> dict:
    """
    Haalt PageSpeed data op voor een URL.
    strategy: 'mobile' of 'desktop'
    Retourneert gestandaardiseerd dict of {"enabled": False, "data": None}.
    """
    if not ENABLED:
        return {"enabled": False, "data": None}

    params = {"url": url, "strategy": strategy, "key": API_KEY}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        categories = raw.get("lighthouseResult", {}).get("categories", {})
        audits = raw.get("lighthouseResult", {}).get("audits", {})

        return {
            "enabled": True,
            "data": {
                "performance_score": round((categories.get("performance", {}).get("score", 0) or 0) * 100),
                "lcp": audits.get("largest-contentful-paint", {}).get("displayValue"),
                "fid": audits.get("max-potential-fid", {}).get("displayValue"),
                "cls": audits.get("cumulative-layout-shift", {}).get("displayValue"),
                "ttfb": audits.get("server-response-time", {}).get("displayValue"),
                "fcp": audits.get("first-contentful-paint", {}).get("displayValue"),
                "speed_index": audits.get("speed-index", {}).get("displayValue"),
                "strategy": strategy,
                "url": url,
            }
        }
    except httpx.HTTPStatusError as e:
        logger.error(f"PageSpeed API error {e.response.status_code} voor {url}: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
    except Exception as e:
        logger.error(f"PageSpeed onverwachte fout voor {url}: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

### `app/integrations/google_crux.py`

```python
"""
Chrome UX Report (CrUX) API adapter.
Geeft real-world laadtijddata van echte Chrome-gebruikers.
Activeren: zet GOOGLE_CRUX_API_KEY in systemd override.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_CRUX_API_KEY", "")
BASE_URL = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
ENABLED = bool(API_KEY)


async def fetch_crux(origin: str, form_factor: str = "PHONE") -> dict:
    """
    Haalt CrUX data op voor een origin (bijv. https://example.com).
    form_factor: 'PHONE', 'DESKTOP', 'TABLET'
    """
    if not ENABLED:
        return {"enabled": False, "data": None}

    payload = {"origin": origin, "formFactor": form_factor}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{BASE_URL}?key={API_KEY}",
                json=payload
            )
            resp.raise_for_status()
            raw = resp.json()

        metrics = raw.get("record", {}).get("metrics", {})

        def p75(metric_key: str):
            m = metrics.get(metric_key, {})
            return m.get("percentiles", {}).get("p75")

        return {
            "enabled": True,
            "data": {
                "origin": origin,
                "form_factor": form_factor,
                "lcp_p75": p75("largest_contentful_paint"),
                "fid_p75": p75("first_input_delay"),
                "cls_p75": p75("cumulative_layout_shift"),
                "inp_p75": p75("interaction_to_next_paint"),
                "ttfb_p75": p75("experimental_time_to_first_byte"),
                "fcp_p75": p75("first_contentful_paint"),
            }
        }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Geen CrUX data beschikbaar voor dit domein
            return {"enabled": True, "data": None, "error": "no_data"}
        logger.error(f"CrUX API error {e.response.status_code} voor {origin}: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
    except Exception as e:
        logger.error(f"CrUX onverwachte fout voor {origin}: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

### `app/integrations/google_natural_language.py`

```python
"""
Google Natural Language API adapter.
Sentimentanalyse, entity-extractie en inhoudsclassificatie voor copy-review.
Activeren: zet GOOGLE_NL_API_KEY in systemd override.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_NL_API_KEY", "")
BASE_URL = "https://language.googleapis.com/v1"
ENABLED = bool(API_KEY)


def _doc(text: str) -> dict:
    return {"document": {"type": "PLAIN_TEXT", "content": text}}


async def analyze_sentiment(text: str) -> dict:
    """Sentimentanalyse: score (-1 tot 1) en magnitude."""
    if not ENABLED:
        return {"enabled": False, "data": None}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{BASE_URL}/documents:analyzeSentiment?key={API_KEY}",
                json=_doc(text)
            )
            resp.raise_for_status()
            raw = resp.json()
        sentiment = raw.get("documentSentiment", {})
        return {
            "enabled": True,
            "data": {
                "score": sentiment.get("score"),
                "magnitude": sentiment.get("magnitude"),
                "sentences": [
                    {
                        "text": s.get("text", {}).get("content"),
                        "score": s.get("sentiment", {}).get("score"),
                    }
                    for s in raw.get("sentences", [])
                ]
            }
        }
    except Exception as e:
        logger.error(f"NL sentiment fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}


async def analyze_entities(text: str) -> dict:
    """Entity-extractie: welke entiteiten worden benoemd en hoe prominent."""
    if not ENABLED:
        return {"enabled": False, "data": None}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{BASE_URL}/documents:analyzeEntities?key={API_KEY}",
                json=_doc(text)
            )
            resp.raise_for_status()
            raw = resp.json()
        return {
            "enabled": True,
            "data": {
                "entities": [
                    {
                        "name": e.get("name"),
                        "type": e.get("type"),
                        "salience": round(e.get("salience", 0), 4),
                    }
                    for e in raw.get("entities", [])
                ]
            }
        }
    except Exception as e:
        logger.error(f"NL entities fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}


async def classify_text(text: str) -> dict:
    """Inhoudsclassificatie: contentkategorieën met confidence score."""
    if not ENABLED:
        return {"enabled": False, "data": None}
    if len(text.split()) < 20:
        # API vereist minimaal ~20 woorden
        return {"enabled": True, "data": None, "error": "text_too_short"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{BASE_URL}/documents:classifyText?key={API_KEY}",
                json=_doc(text)
            )
            resp.raise_for_status()
            raw = resp.json()
        return {
            "enabled": True,
            "data": {
                "categories": [
                    {
                        "name": c.get("name"),
                        "confidence": round(c.get("confidence", 0), 4),
                    }
                    for c in raw.get("categories", [])
                ]
            }
        }
    except Exception as e:
        logger.error(f"NL classify fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}


async def full_analysis(text: str) -> dict:
    """Voert sentiment + entities + classify parallel uit. Entry point voor QA Reviewer."""
    import asyncio
    sentiment, entities, classification = await asyncio.gather(
        analyze_sentiment(text),
        analyze_entities(text),
        classify_text(text),
    )
    return {
        "enabled": ENABLED,
        "sentiment": sentiment.get("data"),
        "entities": entities.get("data"),
        "classification": classification.get("data"),
    }
```

---

### `app/integrations/google_indexing.py`

**Geen import-crash op ongeldige base64:** op module-niveau alleen `ENABLED = bool(os.getenv(...))`. **Base64-decodering en JSON-parse gebeuren uitsluitend in `_get_service_account_credentials()`** wanneer de adapter daadwerkelijk een request doet — zo faalt `import app.integrations.google_indexing` niet als de env-var rommel bevat.

```python
"""
Google Indexing API adapter.
Meldt URL's aan voor Google-indexering via Service Account.
Activeren: zet GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON in systemd override (base64-encoded JSON).
"""
import os
import json
import base64
import logging
import httpx

logger = logging.getLogger(__name__)

_raw = os.getenv("GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON", "")
ENABLED = bool(_raw)

INDEXING_URL = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPES = ["https://www.googleapis.com/auth/indexing"]


def _get_service_account_credentials() -> dict | None:
    if not _raw:
        return None
    try:
        decoded = base64.b64decode(_raw).decode("utf-8")
        return json.loads(decoded)
    except Exception as e:
        logger.error(f"Indexing API: kan service account JSON niet parsen: {e}")
        return None


async def _get_access_token(credentials: dict) -> str | None:
    """Haalt een access token op via JWT voor het service account."""
    try:
        import time
        import jwt  # pip install PyJWT cryptography

        now = int(time.time())
        payload = {
            "iss": credentials["client_email"],
            "scope": " ".join(SCOPES),
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }
        private_key = credentials["private_key"]
        token = jwt.encode(payload, private_key, algorithm="RS256")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": token,
                }
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
    except Exception as e:
        logger.error(f"Indexing API: access token fout: {e}")
        return None


async def request_indexing(url: str, notification_type: str = "URL_UPDATED") -> dict:
    """
    Meldt een URL aan voor Google-indexering.
    notification_type: 'URL_UPDATED' of 'URL_DELETED'
    """
    if not ENABLED:
        return {"enabled": False, "data": None}

    credentials = _get_service_account_credentials()
    if not credentials:
        return {"enabled": True, "data": None, "error": "invalid_credentials"}

    access_token = await _get_access_token(credentials)
    if not access_token:
        return {"enabled": True, "data": None, "error": "token_error"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                INDEXING_URL,
                json={"url": url, "type": notification_type},
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            raw = resp.json()

        return {
            "enabled": True,
            "data": {
                "url": url,
                "type": notification_type,
                "notify_time": raw.get("urlNotificationMetadata", {}).get("latestUpdate", {}).get("notifyTime"),
            }
        }
    except Exception as e:
        logger.error(f"Indexing API fout voor {url}: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

### `app/integrations/google_business_profile.py`

**Geen platform-`ENABLED`:** OAuth-adapters hebben geen env-var die de hele module aan/uit zet. Ze gebruiken alleen een **per-klant `access_token`**; activering = koppeling via Integrations UI (tokens in DB). Zelfde reden voor YouTube, Merchant Center en Sheets hieronder.

```python
"""
Google Business Profile API adapter (voorheen Google My Business).
Reviews, insights en locatiedata per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth). Geen platform-level env var nodig.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://mybusinessaccountmanagement.googleapis.com/v1"
BUSINESS_INFO_URL = "https://mybusinessinformation.googleapis.com/v1"


async def get_locations(access_token: str) -> dict:
    """Haalt alle Business Profile locaties op voor dit account."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Stap 1: account ophalen
            resp = await client.get(
                f"{BASE_URL}/accounts",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            accounts = resp.json().get("accounts", [])
            if not accounts:
                return {"enabled": True, "data": [], "error": "no_accounts"}

            account_name = accounts[0]["name"]

            # Stap 2: locaties ophalen
            resp2 = await client.get(
                f"{BUSINESS_INFO_URL}/{account_name}/locations",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp2.raise_for_status()
            locations = resp2.json().get("locations", [])

        return {
            "enabled": True,
            "data": {
                "account": account_name,
                "locations": [
                    {
                        "name": loc.get("name"),
                        "title": loc.get("title"),
                        "store_code": loc.get("storeCode"),
                    }
                    for loc in locations
                ]
            }
        }
    except Exception as e:
        logger.error(f"Business Profile locations fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}


async def get_reviews(access_token: str, location_name: str) -> dict:
    """Haalt reviews op voor een specifieke locatie."""
    try:
        REVIEWS_URL = "https://mybusiness.googleapis.com/v4"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{REVIEWS_URL}/{location_name}/reviews",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            raw = resp.json()

        reviews = raw.get("reviews", [])
        return {
            "enabled": True,
            "data": {
                "average_rating": raw.get("averageRating"),
                "total_review_count": raw.get("totalReviewCount"),
                "reviews": [
                    {
                        "rating": r.get("starRating"),
                        "comment": r.get("comment", ""),
                        "create_time": r.get("createTime"),
                        "reviewer": r.get("reviewer", {}).get("displayName"),
                    }
                    for r in reviews[:20]  # max 20 meest recente
                ]
            }
        }
    except Exception as e:
        logger.error(f"Business Profile reviews fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

### `app/integrations/google_youtube.py`

*(OAuth — zie Business Profile: geen platform-`ENABLED`.)*

```python
"""
YouTube Data API v3 + YouTube Analytics API adapter.
Channeldata, videometrics en kijkgedrag per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging
import httpx

logger = logging.getLogger(__name__)

DATA_BASE = "https://www.googleapis.com/youtube/v3"
ANALYTICS_BASE = "https://youtubeanalytics.googleapis.com/v2"


async def get_channel_summary(access_token: str) -> dict:
    """Haalt channeldata op: naam, subscribers, views, videocount."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{DATA_BASE}/channels",
                params={"part": "snippet,statistics", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

        if not items:
            return {"enabled": True, "data": None, "error": "no_channel"}

        ch = items[0]
        stats = ch.get("statistics", {})
        return {
            "enabled": True,
            "data": {
                "channel_id": ch.get("id"),
                "title": ch.get("snippet", {}).get("title"),
                "subscriber_count": stats.get("subscriberCount"),
                "view_count": stats.get("viewCount"),
                "video_count": stats.get("videoCount"),
            }
        }
    except Exception as e:
        logger.error(f"YouTube channel fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}


async def get_top_videos(access_token: str, max_results: int = 10) -> dict:
    """Haalt top videos op gesorteerd op views."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{DATA_BASE}/search",
                params={
                    "part": "snippet",
                    "forMine": "true",
                    "type": "video",
                    "order": "viewCount",
                    "maxResults": max_results,
                },
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

        return {
            "enabled": True,
            "data": {
                "videos": [
                    {
                        "video_id": v.get("id", {}).get("videoId"),
                        "title": v.get("snippet", {}).get("title"),
                        "published_at": v.get("snippet", {}).get("publishedAt"),
                        "thumbnail": v.get("snippet", {}).get("thumbnails", {}).get("medium", {}).get("url"),
                    }
                    for v in items
                ]
            }
        }
    except Exception as e:
        logger.error(f"YouTube top videos fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}


async def get_analytics(access_token: str, channel_id: str, start_date: str, end_date: str) -> dict:
    """Haalt YouTube Analytics op: views, watchTime, subscribers."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{ANALYTICS_BASE}/reports",
                params={
                    "ids": f"channel=={channel_id}",
                    "startDate": start_date,
                    "endDate": end_date,
                    "metrics": "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost",
                    "dimensions": "day",
                },
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            raw = resp.json()

        return {
            "enabled": True,
            "data": {
                "headers": [h.get("name") for h in raw.get("columnHeaders", [])],
                "rows": raw.get("rows", []),
            }
        }
    except Exception as e:
        logger.error(f"YouTube analytics fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

### `app/integrations/google_merchant_center.py`

*(OAuth — zie Business Profile: geen platform-`ENABLED`.)*

```python
"""
Google Merchant Center API (Content API for Shopping) adapter.
Productfeed, approve/reject statussen en feed-kwaliteit per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging
import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://shoppingcontent.googleapis.com/content/v2.1"


async def get_account_status(access_token: str, merchant_id: str) -> dict:
    """Haalt accountstatus en openstaande issues op."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{merchant_id}/accountstatuses/{merchant_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            raw = resp.json()

        return {
            "enabled": True,
            "data": {
                "merchant_id": merchant_id,
                "account_level_issues": raw.get("accountLevelIssues", []),
                "products_pending_approval": raw.get("productsStats", {}).get("pendingApproval"),
                "products_disapproved": raw.get("productsStats", {}).get("disapproved"),
                "products_active": raw.get("productsStats", {}).get("active"),
            }
        }
    except Exception as e:
        logger.error(f"Merchant Center account status fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}


async def get_product_statuses(access_token: str, merchant_id: str, max_results: int = 50) -> dict:
    """Haalt productstatus op: goedgekeurd, afgekeurd, reden."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{merchant_id}/productstatuses",
                params={"maxResults": max_results},
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            raw = resp.json()

        resources = raw.get("resources", [])
        return {
            "enabled": True,
            "data": {
                "total": raw.get("nextPageToken"),  # aanwezig = meer pagina's
                "products": [
                    {
                        "product_id": p.get("productId"),
                        "title": p.get("title"),
                        "status": "approved" if not p.get("itemLevelIssues") else "has_issues",
                        "issues": [
                            {
                                "code": issue.get("code"),
                                "servability": issue.get("servability"),
                                "description": issue.get("description"),
                            }
                            for issue in p.get("itemLevelIssues", [])
                        ]
                    }
                    for p in resources
                ]
            }
        }
    except Exception as e:
        logger.error(f"Merchant Center product statuses fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

### `app/integrations/google_knowledge_graph.py`

```python
"""
Google Knowledge Graph API adapter.
Entiteitsdata over merken, personen en bedrijven.
Activeren: zet GOOGLE_KNOWLEDGE_GRAPH_API_KEY in systemd override.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_KNOWLEDGE_GRAPH_API_KEY", "")
BASE_URL = "https://kgsearch.googleapis.com/v1/entities:search"
ENABLED = bool(API_KEY)


async def search_entity(query: str, limit: int = 5) -> dict:
    if not ENABLED:
        return {"enabled": False, "data": None}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                BASE_URL,
                params={"query": query, "limit": limit, "key": API_KEY, "indent": True}
            )
            resp.raise_for_status()
            raw = resp.json()

        items = raw.get("itemListElement", [])
        return {
            "enabled": True,
            "data": {
                "entities": [
                    {
                        "name": item.get("result", {}).get("name"),
                        "description": item.get("result", {}).get("description"),
                        "types": item.get("result", {}).get("@type", []),
                        "score": item.get("resultScore"),
                        "url": item.get("result", {}).get("url"),
                    }
                    for item in items
                ]
            }
        }
    except Exception as e:
        logger.error(f"Knowledge Graph fout voor '{query}': {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

### `app/integrations/google_translate.py`

```python
"""
Google Translate API adapter.
Vertaalt content naar doeltaal.
Activeren: zet GOOGLE_TRANSLATE_API_KEY in systemd override.
LET OP: betaald per karakter (~$20 per 1M tekens). Altijd bewust aanroepen.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
BASE_URL = "https://translation.googleapis.com/language/translate/v2"
ENABLED = bool(API_KEY)


async def translate(text: str, target_language: str, source_language: str | None = None) -> dict:
    """
    Vertaalt tekst naar target_language (bijv. 'nl', 'en', 'de').
    source_language optioneel — wordt auto-gedetecteerd als leeg.
    """
    if not ENABLED:
        return {"enabled": False, "data": None}

    payload = {
        "q": text,
        "target": target_language,
        "format": "text",
        "key": API_KEY,
    }
    if source_language:
        payload["source"] = source_language

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(BASE_URL, json=payload)
            resp.raise_for_status()
            raw = resp.json()

        translated = raw.get("data", {}).get("translations", [{}])[0]
        return {
            "enabled": True,
            "data": {
                "translated_text": translated.get("translatedText"),
                "detected_source_language": translated.get("detectedSourceLanguage"),
                "target_language": target_language,
                "char_count": len(text),
            }
        }
    except Exception as e:
        logger.error(f"Translate API fout: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

### `app/integrations/google_sheets.py`

*(OAuth — zie Business Profile: geen platform-`ENABLED`.)*

```python
"""
Google Sheets API adapter.
Leest briefs en contentkalenders in vanuit Google Sheets per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging
import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"


async def read_sheet(access_token: str, spreadsheet_id: str, range_: str = "Sheet1!A1:Z1000") -> dict:
    """
    Leest een bereik uit een Google Sheet.
    range_: bijv. 'Sheet1!A1:Z100' of 'Contentkalender!A:F'
    """
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{spreadsheet_id}/values/{range_}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            raw = resp.json()

        values = raw.get("values", [])
        if not values:
            return {"enabled": True, "data": {"headers": [], "rows": []}}

        headers = values[0] if values else []
        rows = []
        for row in values[1:]:
            padded = row + [""] * (len(headers) - len(row))
            rows.append(dict(zip(headers, padded)))

        return {
            "enabled": True,
            "data": {
                "spreadsheet_id": spreadsheet_id,
                "range": range_,
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
            }
        }
    except Exception as e:
        logger.error(f"Sheets API fout voor {spreadsheet_id}: {e}")
        return {"enabled": True, "data": None, "error": str(e)}
```

---

## Backend — Registry en router

### `app/integrations/__init__.py` (aanvullen, niet overschrijven)

Voeg toe aan het einde van het bestaande `__init__.py`:

```python
# Google Integrations registry
from app.integrations.google_pagespeed import fetch_pagespeed, ENABLED as PAGESPEED_ENABLED
from app.integrations.google_crux import fetch_crux, ENABLED as CRUX_ENABLED
from app.integrations.google_natural_language import full_analysis as nl_analyze, ENABLED as NL_ENABLED
from app.integrations.google_indexing import request_indexing, ENABLED as INDEXING_ENABLED
from app.integrations.google_knowledge_graph import search_entity, ENABLED as KG_ENABLED
from app.integrations.google_translate import translate, ENABLED as TRANSLATE_ENABLED

GOOGLE_INTEGRATIONS_STATUS = {
    "pagespeed": PAGESPEED_ENABLED,
    "crux": CRUX_ENABLED,
    "natural_language": NL_ENABLED,
    "indexing": INDEXING_ENABLED,
    "knowledge_graph": KG_ENABLED,
    "translate": TRANSLATE_ENABLED,
    # OAuth: geen env-gestuurde ENABLED — UI toont None = "per klant" (tokens in DB)
    "business_profile": None,
    "youtube": None,
    "merchant_center": None,
    "sheets": None,
}
```

---

### `app/routes/google_integrations.py` (nieuw bestand)

```python
"""
Router voor Google Integrations API endpoints.
Prefix: /api/integrations/google
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.integrations import (
    fetch_pagespeed, fetch_crux, nl_analyze, request_indexing,
    search_entity, translate, GOOGLE_INTEGRATIONS_STATUS
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations/google", tags=["google-integrations"])


# --- Status endpoint ---

@router.get("/status")
async def get_integration_status():
    """Retourneert welke Google-integraties actief zijn op platformniveau."""
    return {"status": GOOGLE_INTEGRATIONS_STATUS}


# --- PageSpeed ---

class PageSpeedRequest(BaseModel):
    url: str
    strategy: str = "mobile"

@router.post("/pagespeed")
async def pagespeed(req: PageSpeedRequest):
    result = await fetch_pagespeed(req.url, req.strategy)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="PageSpeed integratie niet actief")
    return result


# --- CrUX ---

class CruxRequest(BaseModel):
    origin: str
    form_factor: str = "PHONE"

@router.post("/crux")
async def crux(req: CruxRequest):
    result = await fetch_crux(req.origin, req.form_factor)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="CrUX integratie niet actief")
    return result


# --- Natural Language ---

class NLRequest(BaseModel):
    text: str

@router.post("/natural-language/analyze")
async def natural_language_analyze(req: NLRequest):
    result = await nl_analyze(req.text)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Natural Language integratie niet actief")
    return result


# --- Indexing ---

class IndexingRequest(BaseModel):
    url: str
    notification_type: str = "URL_UPDATED"

@router.post("/indexing/notify")
async def indexing_notify(req: IndexingRequest):
    result = await request_indexing(req.url, req.notification_type)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Indexing integratie niet actief")
    return result


# --- Knowledge Graph ---

class KGRequest(BaseModel):
    query: str
    limit: int = 5

@router.post("/knowledge-graph/search")
async def knowledge_graph_search(req: KGRequest):
    result = await search_entity(req.query, req.limit)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Knowledge Graph integratie niet actief")
    return result


# --- Translate ---

class TranslateRequest(BaseModel):
    text: str
    target_language: str
    source_language: str | None = None

@router.post("/translate")
async def translate_text(req: TranslateRequest):
    result = await translate(req.text, req.target_language, req.source_language)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Translate integratie niet actief")
    return result
```

---

## `app/main.py` — router toevoegen

Voeg `google_integrations` toe aan de bestaande importlijst in [`app/main.py`](../app/main.py) (`from app.routes import agents, …, integrations, …`) en roep `app.include_router(google_integrations.router)` aan naast de andere `include_router`-regels. Alternatief als aparte regels:

```python
from app.routes import google_integrations
app.include_router(google_integrations.router)
```

---

## Frontend — IntegrationsStatus component

Maak `web_ui/frontend/src/components/integrations/GoogleIntegrationsStatus.jsx`:

- Import `useAuthReady` van **`../../useAuthReady`** (bestand staat naast `App.jsx` onder `src/`, niet onder `hooks/`).
- Gebruik **`apiFetch`** van **`../../apiClient`** — die injecteert de Bearer-token uit de Supabase-session; wacht met fetchen tot `authReady`.

```jsx
/**
 * GoogleIntegrationsStatus.jsx
 * Toont de status van alle Google-integraties.
 * Groen = actief (env var gezet), Grijs = niet gekoppeld, Geel = per klant (OAuth).
 */
import { useState, useEffect } from 'react'
import { useAuthReady } from '../../useAuthReady'
import { apiFetch } from '../../apiClient'

const INTEGRATION_LABELS = {
  pagespeed: 'PageSpeed Insights',
  crux: 'Chrome UX Report',
  natural_language: 'Natural Language',
  indexing: 'Indexing API',
  knowledge_graph: 'Knowledge Graph',
  translate: 'Translate',
  business_profile: 'Business Profile (per klant)',
  youtube: 'YouTube',
  merchant_center: 'Merchant Center',
  sheets: 'Google Sheets',
}

export default function GoogleIntegrationsStatus() {
  const { authReady, session } = useAuthReady()
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authReady) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await apiFetch('/api/integrations/google/status')
        const data = await res.json()
        if (!cancelled) setStatus(data.status)
      } catch (_) {
        if (!cancelled) setStatus(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [authReady, session])

  if (loading) return <p className="text-sm text-gray-400">Laden...</p>
  if (!status) return null

  return (
    <div className="grid grid-cols-2 gap-2">
      {Object.entries(status).map(([key, enabled]) => (
        <div key={key} className="flex items-center gap-2 p-2 rounded bg-gray-800">
          <span
            className={`w-2 h-2 rounded-full flex-shrink-0 ${
              enabled === true
                ? 'bg-green-400'
                : enabled === false
                ? 'bg-gray-500'
                : 'bg-yellow-400'
            }`}
          />
          <span className="text-xs text-gray-300">{INTEGRATION_LABELS[key] || key}</span>
          <span className="ml-auto text-xs text-gray-500">
            {enabled === true ? 'Actief' : enabled === false ? 'Inactief' : 'Per klant'}
          </span>
        </div>
      ))}
    </div>
  )
}
```

---

## Fase-checks (tussenrapportage per fase)

### Na aanmaken adapters

```bash
# Controleer alle bestanden aangemaakt
ls app/integrations/google_*.py

# Syntax check alle nieuwe modules
python3 -c "
import importlib, sys
modules = [
    'app.integrations.google_pagespeed',
    'app.integrations.google_crux',
    'app.integrations.google_natural_language',
    'app.integrations.google_indexing',
    'app.integrations.google_business_profile',
    'app.integrations.google_youtube',
    'app.integrations.google_merchant_center',
    'app.integrations.google_knowledge_graph',
    'app.integrations.google_translate',
    'app.integrations.google_sheets',
]
for m in modules:
    try:
        importlib.import_module(m)
        print(f'OK: {m}')
    except Exception as e:
        print(f'FOUT: {m} — {e}')
"
```

### Na router toevoegen

```bash
sudo systemctl restart wonderz-backend
sleep 3

# Status endpoint moet werken (alle integraties disabled = correct)
curl -s http://localhost:8090/api/integrations/google/status | python3 -m json.tool

# Verwacht output:
# {
#   "status": {
#     "pagespeed": false,
#     "crux": false,
#     "natural_language": false,
#     ...
#   }
# }
```

### Na migratie

```bash
# Voer migratie uit
psql $DATABASE_URL -f app/migrations/083_google_integrations.sql

# Controleer platform_integrations tabel
psql $DATABASE_URL -c "SELECT provider, is_enabled FROM platform_integrations ORDER BY provider;"
```

### Na frontend build

```bash
cd web_ui/frontend && npm run build
```

Controleer: geen build errors, `GoogleIntegrationsStatus` importeerbaar.

---

## Acceptatiecriteria — alles klaar als

- [ ] Alle 10 adapter bestanden aangemaakt in `app/integrations/`
- [ ] `app/routes/google_integrations.py` aangemaakt
- [ ] Router geregistreerd in `app/main.py`
- [ ] `GET /api/integrations/google/status` retourneert alle 10 integraties als `false` of `null`
- [ ] `POST /api/integrations/google/pagespeed` retourneert `503` als key ontbreekt (niet 500)
- [ ] Migratie `083_google_integrations.sql` uitgevoerd, `platform_integrations` tabel bestaat
- [ ] `GoogleIntegrationsStatus.jsx` aangemaakt
- [ ] `npm run build` slaagt zonder errors
- [ ] Backend opnieuw gestart, geen import errors in `journalctl`

---

## Git commit

```bash
git add app/integrations/google_pagespeed.py \
        app/integrations/google_crux.py \
        app/integrations/google_natural_language.py \
        app/integrations/google_indexing.py \
        app/integrations/google_business_profile.py \
        app/integrations/google_youtube.py \
        app/integrations/google_merchant_center.py \
        app/integrations/google_knowledge_graph.py \
        app/integrations/google_translate.py \
        app/integrations/google_sheets.py \
        app/integrations/__init__.py \
        app/routes/google_integrations.py \
        app/main.py \
        app/migrations/083_google_integrations.sql \
        web_ui/frontend/src/components/integrations/GoogleIntegrationsStatus.jsx

git commit -m "feat: add Google integrations architecture (all 10 adapters, disabled by default)"
```
