# Deploy Wonderz

## Frontend (Vercel)

Build is ready in `web_ui/frontend/dist/`.

**Option A – Git (if repo is connected to Vercel)**  
Push to `main`; Vercel will deploy automatically.

**Option B – Vercel CLI**
```bash
npm install -g vercel
cd web_ui/frontend
vercel --prod
```
Set `VITE_API_URL` in Vercel Project Settings → Environment Variables (e.g. `https://wonderz-agentics.fly.dev`).

**Option C – Static host**  
Copy the contents of `web_ui/frontend/dist/` to your web server document root.

---

## Backend (Fly.io)

**Option A – Git**  
Push to `main`; GitHub Actions will run `flyctl deploy --remote-only` if `FLY_API_TOKEN` is set in repo secrets.

**Option B – Fly CLI**
```bash
# Install: https://fly.io/docs/hands-on/install-flyctl/
flyctl auth login
cd ~/wonderz-agentics
fly deploy --app wonderz-agentics
```
Ensure `DATABASE_URL` and other secrets are set: `fly secrets list --app wonderz-agentics`.

---

## Quick reference

| What        | Command / action |
|------------|-------------------|
| Frontend   | Push to `main` or `cd web_ui/frontend && vercel --prod` |
| Backend    | Push to `main` or `fly deploy --app wonderz-agentics` |
| Local API  | `cd ~/wonderz-agentics && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8090` |

Live URLs (from README):  
- Frontend: https://frontend-rho-one-99.vercel.app  
- Backend: https://wonderz-agentics.fly.dev  
