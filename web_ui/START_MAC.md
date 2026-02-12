# 🚀 START GUIDE - MacOS

## Snelle Start (3 stappen)

### Stap 1: Installeer Node.js
Download en installeer van: https://nodejs.org/
(Kies de LTS versie)

### Stap 2: Kopieer web-ui folder
Zet de hele `web-ui` folder in:
```
~/Documents/claude/web-ui/
```

### Stap 3: Start!

Open Terminal en run:
```bash
cd ~/Documents/claude/web-ui
./start.sh
```

Wacht 2-3 minuten (eerste keer installeert dependencies).

Dan opent automatisch: http://localhost:3000

## ✅ Je bent klaar!

---

## 🔧 Als start.sh niet werkt - Manual Start

### Terminal 1 - Backend:
```bash
cd ~/Documents/claude/web-ui/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Terminal 2 - Frontend (nieuw venster):
```bash
cd ~/Documents/claude/web-ui/frontend
npm install
npm run dev
```

Dan open: http://localhost:3000

---

## ❓ Problemen?

**"command not found: node"**
→ Installeer Node.js van https://nodejs.org/

**"Port already in use"**
```bash
# Kill processes
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
# Probeer opnieuw
./start.sh
```

**"API key not configured"**
→ Zorg dat `~/Documents/claude/.env` bestaat met je ANTHROPIC_API_KEY

---

## 🎉 Enjoy!

Open http://localhost:3000 en start je eerste AI project!
