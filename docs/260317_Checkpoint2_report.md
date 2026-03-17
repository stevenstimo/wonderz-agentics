# Checkpoint 2 rapport: available_clients en gsc_properties (Fase 2 Data Agent)

**Datum:** 2025-03-17  
**Doel:** Vóór implementatie van `_detect_task_type` vastleggen hoe clients voor een user en GSC OAuth properties worden opgehaald. Geen stubs of hardcoded lijsten; als iets ontbreekt = blocker.

---

## 1. Clients voor een user (available_clients)

**Tabel:** `clients`  
**Slug-kolom:** `slug` (TEXT NOT NULL, UNIQUE met `user_id`)  
**Schema:** [app/migrations/050_clients_table.sql](app/migrations/050_clients_table.sql) — `client_id`, `user_id`, `client_name`, `slug`, `description`, `is_active`, `created_at`.

**Bestaande patronen in de codebase:**
- Enkele client ophalen: `SELECT slug FROM clients WHERE user_id = $1 AND slug = $2 [AND (is_active IS NULL OR is_active = true)]` — o.a. [app/services/client_mention.py](app/services/client_mention.py) (resolve_client_slug), [app/routes/clients.py](app/routes/clients.py) (meerdere endpoints).
- **Lijst van alle clients voor een user:** Er is een `list_clients` endpoint in [app/routes/clients.py](app/routes/clients.py) (regel 108), maar die query filtert **niet** op `user_id` (alleen `ORDER BY client_name`). Voor intake hebben we expliciet clients voor de job-user nodig.

**Conclusie:** Geen blocker. De tabel en kolom bestaan. We voeren in `run_intake_inline` een query uit:
- `SELECT slug FROM clients WHERE user_id = $1 AND (is_active IS NULL OR is_active = true) ORDER BY slug`
- met `user_id = job_row["user_id"]` → resultaat is de lijst **available_clients** (slugs) voor die user.

---

## 2. GSC OAuth properties (gsc_properties)

**Opslag:** Geen aparte “GSC properties”-tabel. GSC-koppeling en site-URL’s zitten in de **per-client OAuth-config**:

- **Tabel:** `client_integrations`  
- **Kolommen:** `user_id`, `client_slug`, `integration_type`, `extra_config` (JSONB).  
- **GSC-rij:** `integration_type = 'google_search_console'`.  
- **Inhoud `extra_config`:**
  - `site_url`: primaire GSC-site (na OAuth-callback gezet).
  - `gsc_sites`: optionele array met alle site-URL’s die bij de token horen (na `list_gsc_sites(access_token)` in [app/routes/integrations.py](app/routes/integrations.py) regels 484–508).

**Bestaande code:**
- [app/services/seo_gsc_fetcher.py](app/services/seo_gsc_fetcher.py): `get_gsc_site_url_for_client(user_id, client_slug)` haalt **één** `site_url` op uit `client_integrations.extra_config` (en fallback `client_platform_configs.config` voor platform `gsc`).
- Er is geen bestaande helper die de **lijst** van GSC properties (meerdere site-URL’s) voor een client retourneert.

**Conclusie:** Geen blocker. Data zit in `client_integrations` (en eventueel `client_platform_configs`). Voor intake:
- Als we al een **client_slug** hebben: één rij ophalen `WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'google_search_console'`, daarna uit `extra_config` de lijst afleiden: `extra_config->gsc_sites` indien aanwezig, anders `[extra_config->site_url]` als `site_url` bestaat.
- Als we nog geen client hebben (meerdere clients): per client met GSC-integratie dezelfde lookup doen en de lijsten samenvoegen, of voor de completeness-check volstaan met “heeft deze client meerdere GSC sites?” (één rij per client; uit `extra_config` bepalen of er meerdere sites zijn).

Implementatie: kleine helper of inline query in dezelfde flow die `extra_config` uitleest en een lijst site-URL’s retourneert (geen hardcoded array, geen stub).

---

## 3. Samenvatting

| Veld                 | Bron                                      | Query / aanpak |
|----------------------|-------------------------------------------|----------------|
| **available_clients**| Tabel `clients`, kolom `slug`             | `SELECT slug FROM clients WHERE user_id = $1 AND (is_active IS NULL OR is_active = true) ORDER BY slug` |
| **gsc_properties**   | Tabel `client_integrations`, `extra_config` (GSC) | Per (user_id, client_slug) waar bekend: SELECT extra_config WHERE integration_type = 'google_search_console'; lijst = extra_config->gsc_sites of [extra_config->site_url]. |

Beide zijn opvraagbaar via bestaande tabelstructuur; geen blocker. Implementatie sluit aan op deze structuur.
