# Deploy Wonderz

## Deployment Context

| Component | Hosting | Deploy |
|-----------|---------|--------|
| **Backend** | exe.dev server (systemd: `wonderz-backend.service`) | `git pull` → `sudo systemctl restart wonderz-backend` |
| **Frontend** | Vercel | Auto-deploy on push to `main` |
| **Local backend** | — | `http://localhost:8090` |

**Backend URL:** https://wonderz-agentic.exe.xyz

> Fly.io is **niet in gebruik**. Negeer `fly.toml` en alle flyctl configuratie.

---

## Frontend (Vercel)

Build: `web_ui/frontend/dist/`

**Deploy:** Push naar `main` → Vercel deployt automatisch.

**Handmatig (Vercel CLI):**
```bash
cd web_ui/frontend
vercel --prod
```

Stel `VITE_API_URL` in Vercel Project Settings → Environment Variables: `https://wonderz-agentic.exe.xyz`

---

## Backend (exe.dev server)

**Deploy stappen:**
1. `git pull` op de server
2. `sudo systemctl restart wonderz-backend`

Service: `wonderz-backend.service`

---

## Quick reference

| Wat | Actie |
|-----|-------|
| Frontend | Push naar `main` (Vercel auto-deploy) |
| Backend | `git pull` + `sudo systemctl restart wonderz-backend` op server |
| Lokaal | `./start_backend.sh` of `uvicorn app.main:app --host 0.0.0.0 --port 8090` |

**URLs:**
- Backend: https://wonderz-agentic.exe.xyz
- Frontend: Vercel URL (zie Vercel dashboard)
