# 🔗 AI Bureau - Important URLs & Configuration

> **Alle belangrijke URLs in één bestand!** Geen verveling meer met herhaaldelijk invoeren. 

---

## 🚀 Quick Start URLs

### Development (Local)
```
Backend API:      http://localhost:8090
Frontend:         http://localhost:5173
Database:         db.cqasccazioqjodctawzx.supabase.co:5432
API Docs:         http://localhost:8090/docs
Health Check:     http://localhost:8090/health
```

### Production (Fly.io)
```
Backend API:      https://wonderz-agentics.fly.dev
Frontend:         https://wonderz-agentics.vercel.app
Database:         db.cqasccazioqjodctawzx.supabase.co:5432 (shared)
```

---

## 📚 API Endpoints

### Crew Management
- **List Crews**: `GET /api/crew`
- **Create Crew**: `POST /api/crew`
- **Get Crew**: `GET /api/crew/{id}`
- **Update Crew**: `PUT /api/crew/{id}`
- **Delete Crew**: `DELETE /api/crew/{id}`

### Projects
- **List Projects**: `GET /api/projects`
- **Create Project**: `POST /api/projects`
- **Get Project**: `GET /api/projects/{id}`
- **Update Project**: `PUT /api/projects/{id}`
- **Delete Project**: `DELETE /api/projects/{id}`

### Jobs/Tasks
- **List Jobs**: `GET /jobs`
- **Create Job**: `POST /jobs`
- **Get Job**: `GET /jobs/{id}`
- **Answer Job**: `POST /jobs/{id}/answer`
- **Approve Plan**: `POST /jobs/{id}/approve-plan`
- **Request Changes**: `POST /jobs/{id}/request-changes`
- **Give Feedback**: `POST /jobs/{id}/feedback`
- **Approve Job**: `POST /jobs/{id}/approve`

### Other
- **Unified Products**: `GET /api/unified-products`
- **API Docs**: `GET /docs` (Swagger UI)
- **OpenAPI Schema**: `GET /openapi.json`

---

## 🔧 Environment Variables

### Backend Setup
```bash
# Database (Supabase)
DATABASE_URL="postgresql://[user]:[password]@db.cqasccazioqjodctawzx.supabase.co:5432/postgres"

# Other backends might need:
SUPABASE_API_KEY="your_key_here"

# Optional
RUN_MIGRATIONS=false
DEBUG=true
ENV=development  # or "production"
PYTHONPATH=/Users/timo/Documents/Claude
```

### Frontend Setup
```bash
VITE_API_URL="http://localhost:8090"  # local
# or
VITE_API_URL="https://wonderz-agentics.fly.dev"  # production
```

---

## 🎯 Commands to Start Services

### Start Backend (Python)
```bash
# With explicit DATABASE_URL
DATABASE_URL="postgresql://..." PYTHONPATH=/Users/timo/Documents/Claude \
  /Users/timo/Documents/Claude/.venv/bin/python -m uvicorn \
  web-ui.backend.api_main:app --reload --port 8090
```

Or simpler (if DATABASE_URL is in .env):
```bash
cd /Users/timo/Documents/Claude
source .venv/bin/activate
python -m uvicorn web-ui.backend.api_main:app --reload --port 8090
```

### Start Frontend (React/Vite)
```bash
cd /Users/timo/Documents/Claude/web-ui/frontend
VITE_API_URL="http://localhost:8090" npm run dev -- --port 5173
```

### Start Both Services (Quick Script)
```bash
#!/bin/bash
# Save as: start_services.sh

# Start backend in background
echo "Starting backend..."
cd /Users/timo/Documents/Claude
PYTHONPATH=/Users/timo/Documents/Claude \
  python -m uvicorn web-ui.backend.api_main:app --reload --port 8090 &

# Start frontend
echo "Starting frontend..."
cd /Users/timo/Documents/Claude/web-ui/frontend
VITE_API_URL="http://localhost:8090" npm run dev -- --port 5173
```

---

## 📋 Configuration Files

### Python Config
- **Main**: `/Users/timo/Documents/Claude/config.py`
  - Contains `AppConfig` class with all URLs
  - Use: `from config import AppConfig`
  - Call: `AppConfig.print_config()` to see all URLs

### Frontend Config  
- **Vue/React**: `/Users/timo/Documents/Claude/web-ui/frontend/src/config.js`
  - Contains `CONFIG` object with all URLs
  - Use: `import CONFIG from '@/config'`

### Environment Files
- `.env` (root) - Main environment variables
- `.env.development` (if needed) - Dev-specific vars
- `.env.production` (if needed) - Prod-specific vars

---

## ✅ Verification Checklist

Before starting development:

- [ ] Backend running: `curl http://localhost:8090/health`
- [ ] Frontend running: Visit `http://localhost:5173` in browser
- [ ] API docs available: `http://localhost:8090/docs`
- [ ] Database connection working (check backend logs)
- [ ] Frontend can reach backend (check network tab in DevTools)

---

## 🆘 Troubleshooting

### Backend won't start on port 8090
- Check if port is in use: `lsof -i :8090`
- Kill process: `kill -9 <PID>`
- Try different port: `--port 8091`

### Frontend can't reach backend
- Check `VITE_API_URL` is set correctly
- Verify backend is running: `curl http://localhost:8090`
- Check browser console for CORS errors
- Make sure firewall allows localhost connections

### Database connection failing
- Check `DATABASE_URL` in `.env`
- Verify Supabase is accessible: `ping db.cqasccazioqjodctawzx.supabase.co`
- Check if connection string includes password

### Modules not found
- Make sure `PYTHONPATH` is set to workspace root
- Activate virtual environment: `source .venv/bin/activate`
- Install requirements: `pip install -r requirements.txt`

---

## 📞 Quick References

| Component | Local | Production |
|-----------|-------|------------|
| Backend | http://localhost:8090 | https://wonderz-agentics.fly.dev |
| Frontend | http://localhost:5173 | https://wonderz-agentics.vercel.app |
| Database | :5432 on Supabase | :5432 on Supabase |
| Docs | /docs | /docs |
| Health | /health | /health |

---

## 🎓 Using the Config in Code

### Python
```python
from config import AppConfig

# Print all URLs
AppConfig.print_config()

# Get API URL
api_url = AppConfig.get_api_url("/api/crew")
print(api_url)  # http://localhost:8090/api/crew

# Get frontend URL
frontend_url = AppConfig.get_frontend_url("/dashboard")
print(frontend_url)  # http://localhost:5173/dashboard
```

### JavaScript/React
```javascript
import CONFIG from '@/config'

// Get full API URL
const apiUrl = CONFIG.getApiUrl(CONFIG.api.endpoints.crew)
// http://localhost:8090/api/crew

// Get full app URL
const dashboardUrl = CONFIG.getAppUrl(CONFIG.app.pages.dashboard)
// http://localhost:5173/dashboard
```

---

Last updated: 2025-02-12
