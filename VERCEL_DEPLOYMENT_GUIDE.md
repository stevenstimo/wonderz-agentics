# Vercel Frontend Deployment - Stap voor Stap

## 🚀 Optie 1: Via Vercel Dashboard (Makkelijkst)

### Stap 1: Nieuw Project Aanmaken
1. Ga naar https://vercel.com/new
2. Selecteer **"Import Git Repository"**
3. Kies **GitHub** als provider
4. Zoek en selecteer: `stevenstimo/wonderz-agentics`

### Stap 2: Project Configuratie
```
Framework Preset: Vite
Root Directory: web-ui/frontend
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

### Stap 3: Environment Variables
Voeg deze toe in "Environment Variables" sectie:

**⚠️ BELANGRIJK: Wacht tot Render deployment klaar is om de juiste API URL te krijgen**

```
VITE_API_URL=https://wonderz-agentics.onrender.com
```

(Als je Render URL anders is, gebruik die)

```
VITE_SUPABASE_URL=https://cqasccazioqjodctawzx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNxYXNjY2F6aW9xam9kY3Rhd3p4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4MDU0NDEsImV4cCI6MjA4NjM4MTQ0MX0.h8wkn_Tg0pEXmQppnQcRbV7Bxw1pSP_0xPqAnVxLA38
```

### Stap 4: Deploy
Klik op **"Deploy"** → Wacht 2-3 minuten

---

## 🚀 Optie 2: Via Vercel CLI (Sneller)

### Installeer Vercel CLI
```bash
npm install -g vercel
```

### Login
```bash
vercel login
```

### Deploy
```bash
cd web-ui/frontend
vercel --prod
```

Tijdens setup:
- **Set up and deploy?** → `Y`
- **Scope:** → Kies je account
- **Link to existing project?** → `N`
- **Project name:** → `wonderz-agentics`
- **Directory:** → `./`
- **Override settings?** → `N`

---

## ✅ Na Deployment

Je krijgt een URL zoals:
```
https://wonderz-agentics.vercel.app
```

**Test de app:**
1. Open de URL
2. Probeer een agent aan te maken
3. Check of API calls werken

---

## 🔧 Troubleshooting

### Als API calls falen:
1. Check of `VITE_API_URL` correct is ingesteld
2. Verifieer dat Render backend draait
3. Test backend direct: `curl https://wonderz-agentics.onrender.com/api/crew`

### Als build faalt:
1. Check build logs in Vercel dashboard
2. Verifieer dat `web-ui/frontend/package.json` bestaat
3. Test lokaal: `cd web-ui/frontend && npm run build`

### Environment Variables updaten:
1. Ga naar Vercel Dashboard → Je Project → Settings → Environment Variables
2. Edit of voeg toe
3. Redeploy: Settings → Deployments → ... → Redeploy

---

## 📋 Checklist

- [ ] Render backend deployment succesvol
- [ ] Render URL gekopieerd
- [ ] Vercel project aangemaakt
- [ ] Environment variables ingesteld
- [ ] Deployment succesvol
- [ ] Frontend URL werkt
- [ ] API calls naar backend werken
- [ ] Test: agent aanmaken lukt

---

**Hulp nodig?** Check de build logs in Vercel dashboard!
