# Backend Deployment Guide

**Status:** Ready to deploy to Railway/Heroku

## 🚀 Option 1: Deploy to Railway (Recommended)

### Setup
1. Go to https://railway.app
2. Create new project → Deploy from GitHub
3. Select `stevenstimo/wonderz-agentics` repository
4. Configure:
   - **Root Directory**: `.` (root)
   - **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} web_ui.backend.api_main:app`
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

## 🚀 Option 2: Deploy to Heroku

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

## 🐳 Option 3: Docker Deployment

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

1. **Get backend URL** from Railway/Heroku (e.g., `https://wonderz-api.railway.app`)
2. **Update Vercel env vars**:
   - `VITE_API_URL=https://wonderz-api.railway.app`
3. **Redeploy frontend** (auto-triggered or manual)

## 📊 Complete Deployment URLs

After both deployments:
- **Frontend**: https://wonderz-agentics.vercel.app
- **Backend API**: https://wonderz-api.railway.app
- **Database**: Supabase (managed)

## 🔗 Health Checks

Test deployment:
```bash
# Frontend
curl https://wonderz-agentics.vercel.app

# Backend
curl https://wonderz-api.railway.app/api/crew

# API Gateway test
curl https://wonderz-api.railway.app/docs
```

## ⚙️ Files Included

- `Dockerfile` - Production-ready image
- `requirements.txt` - All Python dependencies
- `.dockerignore` - Optimization
- `web-ui/backend/api_main.py` - FastAPI app

---

**Recommended**: Start with Railway (easier setup) or Heroku (more familiar)
