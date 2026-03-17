# Fase 4 — GSC service initialisatie (rapport)

**Doel:** run_data_pipeline moet gsc_service initialiseren via de bestaande GSC OAuth-implementatie. Dit rapport beschrijft hoe dat elders gebeurt, zodat get_gsc_service daarop aansluit.

---

## Bestaande GSC-initialisatie in de codebase

Er is **geen aparte "GSC service" class**. Het patroon is:

1. **Access token ophalen**  
   `get_valid_access_token(conn, user_id, client_slug, "google_search_console")` in [app/services/dashboard.py](app/services/dashboard.py) (rond regel 335).  
   - Leest `client_integrations` (user_id, client_slug, integration_type = 'google_search_console').  
   - Gebruikt `extra_config`: access_token, refresh_token, expires_at.  
   - Vernieuwt token indien verlopen via `_refresh_access_token(refresh_token)` (Google OAuth token endpoint).  
   - Slaat vernieuwde token op in `extra_config` en retourneert de access_token (str) of `None`.

2. **GSC API aanroepen**  
   Met de access_token wordt direct de GSC API aangeroepen:
   - **Dashboard / SEO:** [app/services/dashboard.py](app/services/dashboard.py) — `fetch_gsc(access_token, site_url, start_date, end_date, ...)` (rond regel 689).  
   - Doet meerdere POSTs naar `https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query` met `Authorization: Bearer {access_token}`.  
   - Haalt o.a. `dimensions: ["page"]` op met `rowLimit: GSC_STORAGE_ROW_LIMIT` en bouwt `full_pages` (page, clicks, impressions, ctr, position).  
   - Retourneert o.a. `top_pages: full_pages[:GSC_UI_LIMIT]`.

3. **Waar het wordt gebruikt**  
   - [app/routes/clients.py](app/routes/clients.py) (dashboard): `access_token = await get_valid_access_token(conn, current_user.user_id, slug, "google_search_console")`, daarna `fetch_gsc(access_token, site_url, ...)`.  
   - [app/services/dashboard.py](app/services/dashboard.py) (get_client_seo_summary_for_agent): idem met `pool.acquire()` → conn → get_valid_access_token(conn, user_id, client_slug, "google_search_console").  
   - [app/services/seo_gsc_fetcher.py](app/services/seo_gsc_fetcher.py) (fetch_gsc_for_keywords): idem; token + site_url, dan eigen POST naar searchAnalytics/query.

Conclusie: **GSC = access_token + site_url + httpx POST naar searchAnalytics/query.** Er is geen aparte service-instantie; overal wordt `get_valid_access_token(conn, user_id, client_slug, "google_search_console")` gebruikt en daarna dezelfde API-URL.

---

## Aansluiting get_gsc_service voor DataAgent

- **get_gsc_service(pool, user_id, client_slug)** moet een object retourneren dat een `get_top_pages(site_url, start_date, end_date, dimensions, metrics, limit)`-achtige interface biedt (zoals de spec voor DataAgent verwacht), of `None` als er geen koppeling is.
- Implementatie: een dunne wrapper die (pool, user_id, client_slug) bewaart en in `get_top_pages`:
  1. `async with pool.acquire() as conn` → `get_valid_access_token(conn, user_id, client_slug, "google_search_console")`.  
  2. Bij geen token: `None` retourneren of een exception die DataAgent vangt en omzet in _unavailable_result.  
  3. Met token: POST naar dezelfde `searchAnalytics/query` met `dimensions: ["page"]` en `rowLimit: limit`, response omzetten naar lijst van dicts (page, clicks, impressions, ctr, position) en teruggeven.

Zo sluit get_gsc_service aan op de bestaande OAuth- en API-aanroepen zonder een eigen pad te introduceren.
