# Backend Deployment Guide

**Status:** Deployed on Fly.io

## 🚀 Option 1: Deploy to Fly.io (Current)

### Setup
1. Install Fly CLI
2. Login: `flyctl auth login`
3. Deploy from repo root:
```bash
flyctl deploy -a wonderz-agentics
```

### Environment Variables on Fly
```
ANTHROPIC_API_KEY=sk-...your-key...
DATABASE_URL=postgresql://user:pass@host/db
SUPABASE_URL=https://...
SUPABASE_KEY=...
APPROVAL_USER=admin
APPROVAL_PASS=secure_password
```

### Live Backend URL
- https://wonderz-agentics.fly.dev

---

## 🚀 Option 2: Deploy to Railway (Alternative)

### Setup
1. Go to https://railway.app
2. Create new project → Deploy from GitHub
3. Select `stevenstimo/wonderz-agentics` repository
4. Configure:
   - **Root Directory**: `web-ui/backend`
   - **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} api_main:app`
   - **Python Version**: 3.11

### Environment Variables on Railway
```
ANTHROPIC_API_KEY=sk-...your-key...
DATABASE_URL=postgresql://user:pass@host/db
SUPABASE_URL=https://...
SUPABASE_KEY=...
APPROVAL_USER=admin
APPROVAL_PASS=secure_password
```

### Database Setup
- Use Supabase (already configured)
- Or add PostgreSQL plugin on Railway

---

## 🚀 Option 3: Deploy to Heroku

### Setup
```bash
# Install Heroku CLI
brew tap heroku/brew && brew install heroku

# Login
heroku login

# Create app
heroku create your-app-name

# Set buildpack
heroku buildpacks:set heroku/python

# Deploy
git push heroku main

# Set environment variables
heroku config:set ANTHROPIC_API_KEY=sk-...
heroku config:set DATABASE_URL=postgresql://...
```

---

## 🐳 Option 4: Docker Deployment

### Build Image
```bash
docker build -t wonderz-backend .
docker run -p 8000:8000 wonderz-backend
```

### Push to Container Registry
```bash
docker tag wonderz-backend gcr.io/your-project/wonderz-backend
docker push gcr.io/your-project/wonderz-backend
```

---

## 📋 Pre-deployment Checklist

- ✅ All dependencies in `requirements.txt`
- ✅ Dockerfile configured
- ✅ Environment variables ready
- ✅ Database URL available
- ✅ API key for Anthropic ready
- ✅ CORS configured for frontend domain
- ✅ Health check endpoint available

## ✨ After Backend Deployment

1. **Get backend URL** from your host (e.g., `https://wonderz-agentics.fly.dev`)
2. **Update Vercel env vars**:
   - `VITE_API_URL=https://wonderz-agentics.fly.dev`
3. **Redeploy frontend** (auto-triggered or manual)

## 📊 Complete Deployment URLs

After both deployments:
- **Frontend**: https://frontend-rho-one-99.vercel.app
- **Backend API**: https://wonderz-agentics.fly.dev
- **Database**: Supabase (managed)

## 🔗 Health Checks

Test deployment:
```bash
# Frontend
curl https://frontend-rho-one-99.vercel.app

# Backend
curl https://wonderz-agentics.fly.dev/api/crew

# API Gateway test
curl https://wonderz-agentics.fly.dev/docs
```

## ⚙️ Files Included

- `Dockerfile` - Production-ready image
- `requirements.txt` - All Python dependencies
- `.dockerignore` - Optimization
- `web-ui/backend/api_main.py` - FastAPI app

---

**Recommended**: Start with Railway (easier setup) or Heroku (more familiar)
