# Render Deployment Configuratie

## 🔧 Environment Variables in Render Dashboard

Ga naar Render Dashboard → wonderz-agentics → Environment

Voeg toe:

```
ANTHROPIC_API_KEY=sk-ant-...jouw-api-key...
DATABASE_URL=postgresql://user:pass@host:port/db
SUPABASE_URL=https://...jouw-supabase-url...
SUPABASE_KEY=eyJ...jouw-supabase-anon-key...
APPROVAL_USER=admin
APPROVAL_PASS=jouw-secure-wachtwoord
PORT=10000
PYTHON_VERSION=3.11.0
```

## 🚀 Deploy Settings

### Build Command
```
pip install -r requirements.txt
```

### Start Command
```
gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT api_main:app
```

### Python Version
```
3.11.0
```

### Root Directory
```
web-ui/backend
```

## ✅ Checklist

- [ ] Environment variables toegevoegd
- [ ] Build command geconfigureerd
- [ ] Start command geconfigureerd
- [ ] Python 3.11 geselecteerd
- [ ] Auto-deploy enabled vanaf main branch
- [ ] Health check endpoint: `/api/crew`

## 🔗 Na Deployment

1. Kopieer backend URL van Render (bijv. `https://wonderz-agentics.onrender.com`)
2. Ga naar Vercel → Environment Variables
3. Update `VITE_API_URL` met Render URL
4. Redeploy frontend

## 🐛 Troubleshooting

Als deployment faalt:
1. Check logs: "View Logs" button in Render
2. Verifieer alle environment variables zijn ingesteld
3. Check dat `api_main:app` pad klopt
4. Test lokaal eerst: `docker-compose up`

## 📊 Health Check

Test deployed API:
```bash
curl https://wonderz-agentics.onrender.com/api/crew
```

Verwachte response: `[]` of lijst van crews
