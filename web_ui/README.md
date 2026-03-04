# Multi-Agent Development System - Web UI

🎨 Beautiful web interface voor je AI development agents!

## ✨ Features

- **Modern UI**: Clean, responsive design zoals Lovable
- **Real-time Updates**: Zie de agents live aan het werk via WebSockets
- **Progress Tracking**: Visuele voortgang voor elke stage
- **File Downloads**: Download alle gegenereerde code direct
- **Token Tracking**: Zie hoeveel tokens je gebruikt
- **Easy to Use**: Geen command line nodig!

## 🚀 Quick Start

### Vereisten

- Python 3.9+
- Node.js 18+ (download van https://nodejs.org/)
- Anthropic API key

### Installatie

1. **Kopieer de web-ui folder naar je Documents/claude directory**

2. **Zorg dat je .env file klaar is:**
```bash
cd ~/Documents/claude
# .env moet bestaan met je ANTHROPIC_API_KEY
```

3. **Start alles:**
```bash
cd ~/Documents/claude/web-ui
./start.sh
```

De eerste keer duurt langer (installatie dependencies ~2-3 min).

4. **Open je browser:**
```
http://localhost:3000
```

Dat is alles! 🎉

## 📋 Manual Setup (als start.sh niet werkt)

### Backend Setup
```bash
cd web-ui/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start backend
python main.py
```

### Frontend Setup (in nieuwe terminal)
```bash
cd web-ui/frontend
npm install

# Start frontend
npm run dev
```

## 🎯 Gebruik

1. Open http://localhost:3000
2. Voer je project idee in
3. Kies programmeertaal en platform
4. Klik "Generate Project"
5. Wacht terwijl de agents werken (real-time updates!)
6. Download je code files

## 🏗️ Architectuur

```
web-ui/
├── backend/           # FastAPI server
│   ├── main.py       # API + WebSocket endpoints
│   └── requirements.txt
├── frontend/          # React + Vite
│   ├── src/
│   │   ├── App.jsx   # Main UI component
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
└── start.sh          # One-click startup
```

## 🔧 Development

### Backend
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm run dev
```

### API Documentation
Automatisch beschikbaar op: http://localhost:8000/docs

## 🌐 API Endpoints

- `GET /health` - Health check
- `POST /api/workflow/start` - Start workflow (REST)
- `WS /ws` - WebSocket for real-time updates

## 🎨 Tech Stack

**Backend:**
- FastAPI - Modern Python web framework
- WebSockets - Real-time communication
- Anthropic SDK - Claude API integration

**Frontend:**
- React 18 - UI framework
- Vite - Build tool
- Tailwind CSS - Styling
- Lucide React - Icons

## 💡 Tips

**Performance:**
- Eerste run installeert dependencies (traag)
- Daarna start in ~3 seconden

**Development:**
- Backend auto-reloads bij code changes
- Frontend hot-reloads instantly

**Troubleshooting:**
- Port 3000 bezet? Kill met: `lsof -ti:3000 | xargs kill -9`
- Port 8000 bezet? Kill met: `lsof -ti:8000 | xargs kill -9`
- Dan `./start.sh` opnieuw

## 🔐 Security

- API key nooit in frontend code
- Backend handelt alle API calls
- .env files zijn in .gitignore

## 📝 TODO / Roadmap

- [ ] Download all files as ZIP
- [ ] Save/load project presets
- [ ] Cost calculator before running
- [ ] Edit generated code inline
- [ ] Compare multiple iterations
- [ ] Share projects via URL
- [ ] Dark mode toggle

## 🐛 Known Issues

- WebSocket kan timeout bij zeer lange workflows (>5 min)
  - Oplossing: Use REST endpoint voor lange projecten
- Safari WebSocket issues
  - Oplossing: Gebruik Chrome/Firefox

## 🤝 Contributing

Dit is jouw persoonlijke tool - pas aan zoals je wilt!

Suggesties? Open een issue of PR.

## 📄 License

MIT - Do whatever you want!

---

Gemaakt met ❤️ en Claude AI
