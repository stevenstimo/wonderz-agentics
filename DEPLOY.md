# Deploy Wonderz

## Deployment Context

| Component | Hosting | Deploy |
|-----------|---------|--------|
| **Backend** | exe.dev server (systemd: `wonderz-backend.service`) | `git pull` → `sudo systemctl restart wonderz-backend` |
| **Frontend** | exe.dev server (nginx, statische build) | `npm run build` → `dist/` is live |
| **Local backend** | — | `http://localhost:8090` |

**Backend URL:** https://wonderz-agentic.exe.xyz

> Fly.io is **niet in gebruik**. Negeer `fly.toml` en alle flyctl configuratie.
> **Vercel** wordt **niet** gebruikt voor wonderz-agentic.exe.xyz.

---

## Frontend (exe.dev server)

De live frontend draait als statische build via nginx op de exe.dev server. De `dist/` folder is de live frontend.

**Deploy:**
```bash
cd ~/wonderz-agentics/web_ui/frontend && npm run build
```

---

## Backend (exe.dev server)

**Vereiste environment variabelen** (in systemd service of `.env`):

| Variabele | Beschrijving |
|----------|--------------|
| `SUPABASE_URL` | Supabase project URL (bijv. `https://your-project.supabase.co`). Gebruikt voor JWT-validatie via JWKS (ES256). Zonder dit krijg je "Auth not configured" op /api/clients en andere auth-routes. |
| `DATABASE_URL` | PostgreSQL connection string |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (GA4, Ads, GSC) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI (bijv. `https://wonderz-agentic.exe.xyz/api/integrations/google/callback`) |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads API developer token (vereist voor ads-accounts dropdown). Zet in systemd `Environment=GOOGLE_ADS_DEVELOPER_TOKEN=...` |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | MCC (Manager) customer ID — verplicht als klant-accounts onder een Manager vallen. Zet op het 10-cijferige MCC-ID (bijv. `1234567890`). Zonder dit krijg je PERMISSION_DENIED op het dashboard en ontbreken sub-accounts in de dropdown. |

**Deploy:**
```bash
git pull && sudo systemctl restart wonderz-backend
```

Service: `wonderz-backend.service`

---

## Volledige deploy (beide)

```bash
cd ~/wonderz-agentics && git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build
```

---

## Quick reference

| Wat | Actie |
|-----|-------|
| Frontend | `cd ~/wonderz-agentics/web_ui/frontend && npm run build` |
| Backend | `git pull && sudo systemctl restart wonderz-backend` |
| Volledige deploy | `cd ~/wonderz-agentics && git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build` |
| Lokaal | `./start_backend.sh` of `uvicorn app.main:app --host 0.0.0.0 --port 8090` |

**URLs:**
- Backend: https://wonderz-agentic.exe.xyz
- Frontend: wonderz-agentic.exe.xyz (nginx op exe.dev server)
