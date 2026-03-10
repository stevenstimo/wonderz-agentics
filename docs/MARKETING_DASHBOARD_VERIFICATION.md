# Marketing Dashboard — Verificatie & Deploy

## Stap 0 — Property/Account/Site endpoints testen (na OAuth)

Na Google OAuth worden properties/accounts/sites automatisch opgehaald via dropdowns. Handmatig testen:

1. JWT ophalen (zie Stap 1 hieronder)
2. Voer uit (vervang `<token>` en `asured` met client slug):
```bash
# GA4 properties
curl -s -H "Authorization: Bearer <token>" \
  "http://localhost:8090/api/clients/asured/google/ga4-properties"

# Google Ads accounts
curl -s -H "Authorization: Bearer <token>" \
  "http://localhost:8090/api/clients/asured/google/ads-accounts"

# GSC sites
curl -s -H "Authorization: Bearer <token>" \
  "http://localhost:8090/api/clients/asured/google/gsc-sites"
```

**Verwachte response formaten:**
- `ga4-properties`: `[{ "property_id": "123456789", "display_name": "My GA4 Property" }]`
- `ads-accounts`: `[{ "customer_id": "1234567890", "descriptive_name": "Account Name" }]`
- `gsc-sites`: `[{ "site_url": "https://example.com/", "permission_level": "siteOwner" }]`

Bij 404: integratie niet verbonden. Bij 401: token verlopen → "Herverbind Google" in de UI.

---

## Stap 1 — JWT ophalen en dashboard endpoint testen

1. Open de browser op de ingelogde app (bijv. http://localhost:3001 of https://wonderz-agentic.exe.xyz)
2. Open DevTools (F12) → Console
3. Run:
```javascript
const { data } = await window.supabase?.auth?.getSession?.() ?? {};
console.log(data?.session?.access_token);
```
4. Kopieer het token (zonder aanhalingstekens)
5. Voer uit in de terminal:
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8090/api/clients/asured/dashboard?start=2026-02-01&end=2026-03-11"
```
6. Plak de volledige JSON response. Controleer:
   - `overview`: users, sessions, conversions, total_cost, cpa
   - `ga4`: `not_connected: true` of `{ kpis, timeseries, traffic_by_channel }`
   - `google_ads`: `not_connected: true` of `{ campaigns, timeseries }`
   - `gsc`: `not_connected: true` of `{ totals, top_queries, top_pages, timeseries }`

---

## Stap 2 — Vergelijk met GA4

Als `ga4` echte data bevat:
1. Open [Google Analytics](https://analytics.google.com) voor deze client
2. Zet dezelfde datumrange (2026-02-01 t/m 2026-03-11)
3. Vergelijk **Users** en **Sessions** met de dashboard
4. Afwijking > 5%? Controleer `property_id` in client_platform_configs:
   - Ga naar `/clients/vitbliss/integrations`
   - Bij GA4 (als verbonden): vul Property ID in (bijv. `123456789`)
   - Property ID vind je in GA4: Admin → Property Settings → Property ID

---

## Stap 3 — Integrations dropdowns (Asured)

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Ga naar `/clients/asured/integrations` | Pagina laadt, Google verbonden |
| 2 | GA4 dropdown | Laadt properties via API, toont "Properties laden..." tijdens fetch |
| 3 | Google Ads dropdown | Laadt accounts via API (vereist GOOGLE_ADS_DEVELOPER_TOKEN) |
| 4 | GSC dropdown | Laadt sites via API |
| 5 | Selecteer property/account/site | Opslaan via POST /platforms, daarna dashboard toont data |
| 6 | Bij 401 (token verlopen) | "Herverbind Google" knop zichtbaar |

---

## Stap 4 — Vier handmatige checks in de browser

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Ga naar `/clients/asured/dashboard` | Pagina laadt zonder console errors |
| 2 | Verander de datumrange (start/end) | Loading skeleton, daarna nieuwe data |
| 3 | Welke blokken tonen lege states? | Alleen blokken met `not_connected` |
| 4 | Klik "Verbind GA4/Ads/GSC" in een lege state | Navigeert naar `/clients/asured/integrations` |

Fix wat niet werkt vóór deploy.

---

## Stap 5 — Deploy naar productie

```bash
cd /home/exedev/wonderz-agentics
~/commit.sh "feat: marketing dashboard per client met GA4, Ads, GSC"
git push origin main
sudo fuser -k 8090/tcp && sudo systemctl restart wonderz-backend
```

- Vercel deployt automatisch op push naar main
- Test daarna op: https://wonderz-agentic.exe.xyz/clients/asured/dashboard

---

## Stap 6 — Google property/account/site selectie (dropdowns)

Na OAuth verbinding tonen GA4, Google Ads en GSC een **dropdown** met beschikbare properties/accounts/sites. Selectie wordt automatisch opgeslagen via `POST /api/clients/{slug}/platforms`.

### GOOGLE_ADS_DEVELOPER_TOKEN (vereist voor ads-accounts dropdown)

1. Log in op [Google Ads](https://ads.google.com) met een manager account
2. Ga naar **Tools & Settings** → **API Center** (of direct: https://ads.google.com/aw/apicenter)
3. Vul het API Access formulier in, accepteer de voorwaarden
4. Je krijgt een **Developer Token** (22 karakters, alfanumeriek)
5. Zet op de server in `~/.bashrc` of systemd Environment:
   ```bash
   export GOOGLE_ADS_DEVELOPER_TOKEN="jouw-token-hier"
   ```
6. Herstart de backend: `sudo systemctl restart wonderz-backend`

**Let op:** Test Account Access werkt alleen met test-accounts. Voor productie heb je Basic/Standard Access nodig (review door Google).

### Dropdown flow

- **GA4**: Selecteer property uit dropdown → `config.property_id` wordt opgeslagen
- **Google Ads**: Selecteer account uit dropdown → `config.customer_id` wordt opgeslagen
- **GSC**: Selecteer site uit dropdown → `config.site_url` wordt opgeslagen

Bij token verlopen: toon "Herverbind Google" knop, klik om OAuth opnieuw te doorlopen.
