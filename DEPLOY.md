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
| `SUPABASE_JWT_SECRET` | JWT secret uit Supabase (Project Settings → API → JWT Secret). Zonder dit krijg je "Auth not configured" op /api/clients en andere auth-routes. |
| `DATABASE_URL` | PostgreSQL connection string |

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
