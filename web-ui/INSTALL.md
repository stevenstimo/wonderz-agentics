# 🎨 Multi-Agent Development System - Web UI

## ✨ Wat is dit?

Een **prachtige web interface** voor je multi-agent development system!

Geen command line meer nodig - alles in je browser zoals Lovable! 🚀

### Screenshots Concept:
```
┌─────────────────────────────────────────────┐
│  🌟 Multi-Agent Dev System                  │
│  Transform ideas into production code       │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  Project Idea:                              │
│  [Text area for your idea...]               │
│                                             │
│  Language: [Python ▼]  Platform: [Docker ▼]│
│                                             │
│  [✨ Generate Project]                      │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  Progress:                                  │
│  ⚡ Initialization      ✅                  │
│  📋 Product Owner      ✅                   │
│  💻 Developer          🔄 Working...        │
│  🔍 Reviewer           ⏳ Pending           │
│  🐳 DevOps             ⏳ Pending           │
└─────────────────────────────────────────────┘
```

## 📦 Wat zit erin?

### Backend (FastAPI)
- Real-time WebSocket updates
- REST API endpoints
- Integreert met je bestaande agents
- Automatische health checks

### Frontend (React + Vite)
- Modern, responsive UI
- Real-time progress tracking
- Download generated files
- Token usage tracking
- Mooie gradient design

## 🚀 Installatie op Mac

### Vereisten

**1. Node.js (JavaScript runtime)**
```bash
# Download van: https://nodejs.org/
# Kies: LTS versie (bijv. v20.x.x)
# Installeer via de .pkg installer
```

**2. Python 3.9+** (heb je al!)

**3. API Key** (heb je al in .env!)

### Setup Stappen

**1. Download deze web-ui folder**

Zet hem in:
```
~/Documents/claude/web-ui/
```

Je folder structuur wordt:
```
~/Documents/claude/
├── .env                    # Je API key (al aanwezig)
├── agents/                 # Je agents (al aanwezig)
├── config.py              # Config (al aanwezig)
├── orchestrator.py        # Orchestrator (al aanwezig)
└── web-ui/                # 👈 NIEUW!
    ├── backend/
    ├── frontend/
    ├── start.sh
    └── README.md
```

**2. Check je .env file**

Zorg dat `~/Documents/claude/.env` bestaat met:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-jouw-werkende-key
```

**3. Start het systeem!**

Open Terminal:
```bash
cd ~/Documents/claude/web-ui
chmod +x start.sh
./start.sh
```

**Eerste keer duurt 2-3 minuten** (installeert alles).

Daarna opent automatisch: **http://localhost:3000**

## 🎯 Gebruik

1. **Open browser** → http://localhost:3000
2. **Voer project idee in** 
   - Bijv: "Een blog API met FastAPI en PostgreSQL"
3. **Kies opties**
   - Taal: Python, JavaScript, etc.
   - Platform: Docker, Kubernetes, etc.
4. **Klik "Generate Project"**
5. **Wacht en zie real-time updates!** ✨
   - Initialization
   - Product Owner analyzing...
   - Developer writing code...
   - Reviewer checking...
   - DevOps creating deployment...
6. **Download je files** 📥
   - Alle code files
   - Dockerfile
   - CI/CD configs

## 📊 Features

### Real-time Progress
- ⚡ Live updates via WebSockets
- 🎨 Mooie visuele progress indicators
- ⏱️ Token tracking per stage

### File Downloads
- 💾 Download individuele files
- 📦 (Coming soon: ZIP all files)

### Code Preview
- 👀 Zie generated code
- 📝 Syntax highlighting (coming)

### Statistics
- 📊 Total tokens gebruikt
- 💰 Cost estimation
- 📈 Files generated

## 🔧 Development

Als je de UI wilt aanpassen:

### Backend wijzigen
```bash
cd ~/Documents/claude/web-ui/backend
source venv/bin/activate
# Edit main.py
python main.py  # Test
```

### Frontend wijzigen
```bash
cd ~/Documents/claude/web-ui/frontend
# Edit src/App.jsx
npm run dev  # Auto-reload!
```

## 🐛 Troubleshooting

### "command not found: node"
```bash
# Installeer Node.js:
# Download van https://nodejs.org/
# Gebruik de .pkg installer
# Herstart Terminal
node --version  # Check
```

### "Port 3000 already in use"
```bash
# Kill het process:
lsof -ti:3000 | xargs kill -9
./start.sh  # Probeer opnieuw
```

### "Port 8000 already in use"
```bash
# Kill het process:
lsof -ti:8000 | xargs kill -9
./start.sh  # Probeer opnieuw
```

### "API key not configured"
```bash
# Check .env:
cat ~/Documents/claude/.env

# Moet bevatten:
ANTHROPIC_API_KEY=sk-ant-api03-...

# Niet aanwezig? Maak aan:
nano ~/Documents/claude/.env
# Plak je key, save met Ctrl+O, Enter, Ctrl+X
```

### "WebSocket connection failed"
```bash
# Backend draait niet, start handmatig:
cd ~/Documents/claude/web-ui/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Dependencies niet geïnstalleerd
```bash
# Backend:
cd ~/Documents/claude/web-ui/backend
source venv/bin/activate
pip install -r requirements.txt

# Frontend:
cd ~/Documents/claude/web-ui/frontend
npm install
```

## 🎨 Tech Stack

**Backend:**
- FastAPI (Python web framework)
- WebSockets (real-time)
- Uvicorn (ASGI server)

**Frontend:**
- React 18
- Vite (build tool)
- Tailwind CSS (styling)
- Lucide React (icons)

## 📝 Next Steps

**Nu:**
- ✅ Start de UI: `./start.sh`
- ✅ Test met een project
- ✅ Download je eerste generated code!

**Later:**
- 🎨 Customize de UI naar je smaak
- 🔧 Add extra features
- 📦 Deploy online (optional)

## 💡 Tips

**Performance:**
- Backend start in ~2 seconden
- Frontend hot-reload is instant
- WebSocket = real-time updates!

**Workflow:**
- Start servers eenmaal
- Laat ze draaien
- Refresh browser om opnieuw te starten

**Cost:**
- Zelfde API kosten als CLI versie
- ~$0.10-0.50 per project

## 🆘 Hulp Nodig?

Check:
1. START_MAC.md - Simpele Mac guide
2. README.md - Volledige docs
3. Backend logs - Zie errors in Terminal 1
4. Frontend logs - Zie errors in Terminal 2
5. Browser console - F12 voor dev tools

## 🎉 Enjoy!

Je hebt nu een **Lovable-achtige interface** voor je AI agents!

Build amazing projects! 🚀✨

---

Made with ❤️ and Claude AI
