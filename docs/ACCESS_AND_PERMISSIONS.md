# Toegang en rechten in Wonderz (voor code-niveau antwoorden)

Dit document legt uit waar in de codebase je antwoorden vindt over **gebruikers**, **rollen**, **Client-data** en **toegangsrechten**. Handig voor o.a. veiligheidsbeheer, troubleshooting en vragen zoals: “Heeft gebruiker X toegang tot Client Y?”

---

## 1. Gebruikers-ID en e-mail

### Waar staat gebruikersinformatie?

- **Identiteit** komt uit **Supabase Auth**: gebruikers staan in `auth.users` (Supabase-project).
- De **backend** leest geen gebruikerslijst uit de database; bij elke request wordt de **JWT** gevalideerd. Daaruit komen:
  - **`sub`** → `user_id` (UUID)
  - **`email`** → e-mailadres (indien in token)

Relevante code:

- **Backend (FastAPI):** `app/middleware/auth.py`
  - `_get_current_user_impl`: leest JWT, haalt `sub` (user_id) en `email` uit de payload.
  - `TokenPayload`: bevat `user_id`, `role`, `email`.

### Hoe vind je het user_id of e-mail van iemand (bijv. Mr. Klein)?

1. **Supabase Dashboard**  
   In het Supabase-project: **Authentication → Users**. Daar staan alle gebruikers met o.a. UUID (id) en e-mail.

2. **Directe database-query** (als je toegang hebt tot de Supabase/Postgres-database):
   - Gebruikers (id, email): tabel `auth.users` (Supabase schema).
   - Rollen: tabel `user_roles` (zie hieronder).

Er is **geen** API in de Wonderz-backend die een lijst van alle gebruikers teruggeeft; die informatie komt uit Supabase Auth (Dashboard of DB).

---

## 2. Rollen- en permissiemodel

### Rollen

- **Enum:** `app_role` = `'member'` | `'super_admin'`.
- **Tabel:** `user_roles` met o.a. `user_id` (FK naar `auth.users.id`), `role`, `created_at`, `updated_at`.
- **Migratie (Supabase):** `web_ui/supabase/migrations/20260214133000_create_user_roles.sql`.

### Waar wordt de rol bepaald?

- **Backend:** `app/middleware/auth.py`
  - Rol wordt opgehaald met: `SELECT role FROM user_roles WHERE user_id = $1`.
  - **Fallback:** als het e-mailadres gelijk is aan `SUPER_ADMIN_EMAIL`, krijgt de gebruiker altijd de rol `super_admin`, ongeacht wat in `user_roles` staat.
- **Super-admin e-mail** (hardcoded):  
  `SUPER_ADMIN_EMAIL = "stevenstimo@gmail.com"` in o.a.:
  - `app/middleware/auth.py`
  - `app/routes/settings.py`
  - `web_ui/frontend/src/authz.js`
  - `api_main.py` (web_ui backend)

### Endpoints die super_admin vereisen

- **`require_super_admin`** (dependency in `app/middleware/auth.py`): geeft 403 als `role != 'super_admin'`.
- Gebruikt o.a. in:
  - `app/routes/agents.py` (gehele router)
  - `app/routes/hr.py` (bijv. weekly report)
  - `app/routes/settings.py` (bepaalde acties)
- In `api_main.py`: o.a. settings, en diverse admin-endpoints via `require_super_admin`.

**Conclusie:** Het actieve rollenmodel in de Wonderz-instantie is: **member** (standaard) en **super_admin** (via `user_roles` of via `SUPER_ADMIN_EMAIL`). Er zijn geen andere rollen in de code.

---

## 3. Client-data en toegang

### Welke Client-datasets bestaan?

- **Tabel:** `clients`  
  **Migratie:** `app/migrations/050_clients_table.sql`
- Kolommen o.a.: `client_id`, `user_id`, `client_name`, `slug`, `description`, `is_active`, `created_at`.
- **Uniek per gebruiker:** `(user_id, slug)`.

Gerelateerde tabellen (altijd gekoppeld aan een gebruiker en een client-slug):

- `client_platform_configs`: per client platformconfiguratie (`user_id`, `client_slug`).
- `client_integrations`: integraties (bijv. GA4, Google Ads) per client (`user_id`, `client_slug`).

### Toegangsregel voor Client-data

- **Elke** client-API filtert op de **ingelogde gebruiker**:
  - `WHERE user_id = $1` met `current_user.user_id` (uit JWT).
- Relevante code: `app/routes/clients.py`
  - Bijv. `list_clients`: `WHERE user_id = $1` met `current_user.user_id`.
  - `get_client`, `get_client_dashboard`, en alle andere client-endpoints gebruiken dezelfde `current_user.user_id` voor alle queries op `clients`, `client_platform_configs` en `client_integrations`.

Er is **geen** cross-user toegang: een gebruiker ziet alleen clients waarvan `clients.user_id` gelijk is aan zijn eigen `user_id`. Ook een `super_admin` heeft in de huidige code **geen** speciale “zie alle clients”-logica; toegang blijft per user_id.

### Samenvatting antwoord “Heeft gebruiker X toegang tot Client Y?”

1. **user_id van X** bepalen (Supabase Dashboard of `auth.users`).
2. **Client Y** identificeren (bijv. `slug` of `client_id`).
3. In de database: bestaat er een rij in `clients` met `user_id = <user_id van X>` en de betreffende client (slug/client_id)?  
   - **Ja** → die gebruiker heeft toegang tot die client in de app.  
   - **Nee** → geen toegang (geen andere route of rol die dat overschrijft).

---

## 4. Overzicht: waar in de code kijken

| Vraag | Waar te kijken |
|--------|------------------|
| Gebruikers-ID / e-mail | Supabase Dashboard (Authentication → Users) of tabel `auth.users`. JWT-afhandeling: `app/middleware/auth.py` (TokenPayload, user_id, email). |
| Rollen (member / super_admin) | Tabel `user_roles`. Logica: `app/middleware/auth.py` (+ `SUPER_ADMIN_EMAIL`). Migratie: `web_ui/supabase/migrations/20260214133000_create_user_roles.sql`. |
| Welke clients bestaan / bij welke user | Tabel `clients` (o.a. `user_id`, `slug`, `client_name`). Migratie: `app/migrations/050_clients_table.sql`. |
| Toegang tot een specifieke client | `app/routes/clients.py`: overal `current_user.user_id`; vergelijk met `clients.user_id` voor die client. |
| Welke endpoints super_admin vereisen | `require_super_admin` in `app/middleware/auth.py`; gebruik in o.a. `app/routes/agents.py`, `app/routes/hr.py`, `app/routes/settings.py`, en `api_main.py`. |
| Agent/Job-permissies | `agents/agent_permissions.py` (tool-whitelists per agent). Geen apart “Client-toegang”-model; agent draait in context van de ingelogde gebruiker. |

---

## 5. Audit-logs en dataflow (indicatief)

- **Backend:** errors en belangrijke events worden o.a. gelogd naar o.a. `job_steps.error_log` bij agent-failures (zie project-conventies). Er is geen aparte “audit”-tabel voor alle data-toegang in de code gedocumenteerd.
- **Dataflow naar Client-informatie:**  
  Request → JWT validatie (`auth.py`) → `current_user.user_id` → alle client-queries in `app/routes/clients.py`, `app/services/dashboard.py`, en gerelateerde services gebruiken deze `user_id` voor `clients`, `client_integrations` en `client_platform_configs`.

Met dit document kan iemand (bijv. Mr. Klein) puur op basis van de code en database-structuur nauwkeurig antwoorden over gebruikers, rollen en toegang tot Client-data in Wonderz.
