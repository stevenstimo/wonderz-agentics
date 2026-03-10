# Marketing Dashboard — Verificatie & Deploy

## Stap 1 — JWT ophalen en endpoint handmatig testen

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
  "http://localhost:8090/api/clients/vitbliss/dashboard?start=2026-02-01&end=2026-03-11"
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

## Stap 3 — Vier handmatige checks in de browser

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Ga naar `/clients/vitbliss/dashboard` | Pagina laadt zonder console errors |
| 2 | Verander de datumrange (start/end) | Loading skeleton, daarna nieuwe data |
| 3 | Welke blokken tonen lege states? | Alleen blokken met `not_connected` |
| 4 | Klik "Verbind GA4/Ads/GSC" in een lege state | Navigeert naar `/clients/vitbliss/integrations` |

Fix wat niet werkt vóór deploy.

---

## Stap 4 — Deploy naar productie

```bash
cd /home/exedev/wonderz-agentics
~/commit.sh "feat: marketing dashboard per client met GA4, Ads, GSC"
git push origin main
sudo fuser -k 8090/tcp && sudo systemctl restart wonderz-backend
```

- Vercel deployt automatisch op push naar main
- Test daarna op: https://wonderz-agentic.exe.xyz/clients/vitbliss/dashboard

---

## Stap 5 — Google Ads & GSC configureren (als not_connected)

### GOOGLE_ADS_DEVELOPER_TOKEN

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

### customer_id (Google Ads)

1. Ga naar `/clients/vitbliss/integrations`
2. Bij **Google Ads** (als verbonden): vul **Customer ID** in
3. Formaat: `123-456-7890` (met streepjes) of `1234567890`
4. Customer ID vind je in Google Ads: rechtsboven naast het account-icoon, of in **Tools** → **Setup** → **Accounts**

### site_url (Search Console)

1. Ga naar `/clients/vitbliss/integrations`
2. Bij **Google Search Console** (als verbonden): vul **Site URL** in
3. Formaat: `https://www.vitbliss.nl/` of `sc-domain:vitbliss.nl` (voor domain properties)
4. Moet exact overeenkomen met de property in Search Console

### property_id (GA4, optioneel)

- Als niet ingevuld: de eerste beschikbare GA4 property wordt gebruikt
- Voor meerdere properties: vul het Property ID in (Admin → Property Settings in GA4)
