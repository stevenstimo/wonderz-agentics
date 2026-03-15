# --- Fly.io Deployment ---

## Deployen naar Fly.io

1. Zorg dat je een Fly.io app hebt aangemaakt (appnaam: wonderz-agentics).
2. Maak een Managed Postgres database aan via `fly postgres create` of `fly mpg create`.
3. Koppel de database aan je app en kopieer de DATABASE_URL.
4. Zet de DATABASE_URL als secret:
    fly secrets set DATABASE_URL="postgres://<user>:<password>@<host>:<port>/<db>" --app wonderz-agentics
5. Deploy de app:
    fly deploy --app wonderz-agentics

De backend verwacht dat de DATABASE_URL als environment variable is gezet (zie .env.local.example).

---
# AI Bureau - Multi-Agent Development System

A comprehensive multi-agent system using Claude AI for orchestrated software development with production-grade reliability, error handling, and deployment capabilities.

## 🌐 Live URLs

- **Frontend**: https://frontend-rho-one-99.vercel.app
- **Backend API**: https://wonderz-agentics.fly.dev

## ✨ Features

### Phase 1-4: Core System (✅ Complete)
- ✅ FastAPI REST API with async/await
- ✅ PostgreSQL database with job tracking
- ✅ WebSocket support for real-time updates
- ✅ Multi-agent coordination (Dev, DevOps, Reviewer, Product Owner)
- ✅ Docker containerization and deployment

### Phase 5: Error Handling & Validation (✅ Complete)
- ✅ **5a**: LLM error handling with timeout retry logic and JSON parse fallbacks
- ✅ **5b**: Celery task error handling with exponential backoff and dead-letter queues
- ✅ **5c**: API input validation using Pydantic models
- ✅ **5d**: Database constraints (foreign keys, status transitions, triggers)

### Phase 6: Integration & Deployment (✅ Complete)
- ✅ Comprehensive integration tests
- ✅ Production deployment guide (VM, Kubernetes)
- ✅ API documentation with examples
- ✅ Database migration system
- ✅ Monitoring and troubleshooting guides

## 🏗️ System Architecture

```
User Request
    ↓
API Gateway (FastAPI)
    ├─→ Intake Engine (CEO Agent) - Clarification questions
    ├─→ Strategy Room (StrategyRoom) - Plan generation
    ├─→ Operations Manager - Workflow coordination
    │   ├─→ Developer Agent - Code generation
    │   ├─→ DevOps Agent - Infrastructure
    │   └─→ Reviewer Agent - Quality assurance
    ├─→ Celery Task Queue - Async processing
    └─→ PostgreSQL - State persistence
```

## 📊 Job Workflow

```
INTAKE_CLARIFICATION 
  ↓ (CEO asks clarifications)
  ├─ (user answers) → PLAN_PROPOSED
  │   ↓ (user approves) → RUNNING
  │   │  ├─ (dev work) → JOB_READY
  │   │  └─ (feedback) → RUNNING
  │   └─ (user reconsiders) → INTAKE_CLARIFICATION
  └─ (no clarifications) → PLAN_PROPOSED
```

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose
- Claude API key (from https://console.anthropic.com)

## Database

Applicatiedata draait op **Supabase** (project: `cqasccazioqjodctawzx`). Lokale PostgreSQL wordt alleen nog als backup bewaard, niet meer als primaire DB. BGE-M3-embeddings draaien lokaal op exe.dev en schrijven naar Supabase.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Configure Environment

Create `.env` file (see `.env.example` for a template):
```bash
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_bureau
REDIS_URL=redis://localhost:6379/0
```

#### Email Intake Channel (Gmail)

Jobs can be created by sending an email to a dedicated Gmail inbox. The backend polls via IMAP and creates a job in `PLAN_PROPOSED` for the user linked to the sender address.

- **Setup**: Copy `.env.example` and set `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`. Use a [Gmail App Password](https://support.google.com/accounts/answer/185833) (not your normal password); 2-Step Verification must be enabled. Optionally set `EMAIL_POLL_INTERVAL` (default 60 seconds).
- **Tables**: Ensure migrations `063_inbound_emails_and_users.sql` and `064_jobs_intake_source.sql` are applied. Sender matching uses the `users` table (`id`, `email`); keep it in sync with your auth (e.g. on login).
- **Security**: Never commit `.env`. `GMAIL_APP_PASSWORD` must stay in `.env` only (see `.gitignore`).

### 3. Start Services

**Terminal 1: Database & Cache**
```bash
docker-compose up -d
```

**Terminal 2: API Server**
```bash
uvicorn app.main:app --reload
```

**Terminal 3: Celery Worker**
```bash
celery -A workers.celery_app worker --loglevel=info
```

**Terminal 4: Access**
```bash
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 4. Run Tests

```bash
# All tests (27+ passing)
pytest tests/ -v

# Specific suite
pytest tests/test_job_flow.py -v
pytest tests/test_integration.py -v
```

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment guide (VM, K8s, Docker) |
| [API.md](API.md) | REST API documentation with examples |
| [STRUCTURE.md](STRUCTURE.md) | Project structure and code organization |
| [TESTING.md](TESTING.md) | Testing strategies and test suites |
| [FEATURES.md](FEATURES.md) | Detailed feature descriptions |
| [docs/ACCESS_AND_PERMISSIONS.md](docs/ACCESS_AND_PERMISSIONS.md) | Gebruikers, rollen, Client-toegang en permissiemodel (voor support/veiligheid) |

## 🔧 Key Technologies

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI, Uvicorn, Pydantic |
| **Async** | Celery, Redis, asyncio |
| **Database** | PostgreSQL, asyncpg |
| **LLM** | Claude API via Anthropic |
| **Deployment** | Docker, Docker Compose, Kubernetes |
| **Testing** | pytest, pytest-asyncio |

## 📈 Error Handling

### LLM Failures
- Timeout retry with exponential backoff (1s, 2s, 4s)
- Rate limit backoff (2s, 4s, 8s)
- JSON parse fallback with structured default

### Celery Tasks
- Max 3 retries per task
- Soft timeout: 540s, Hard timeout: 600s
- Dead-letter queue for permanent failures
- Exponential backoff: BASE × 2^(retry_count)

### API Validation
- UUID format validation on all resource IDs
- Pydantic models for input validation
- Status code mapping (201, 400, 404, 422, 500)
- Comprehensive error messages

### Database Constraints
- Foreign key constraints
- Status transition validation
- Unique constraints
- Automatic timestamp triggers

## 🔍 Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Logs
```bash
# API
docker-compose logs -f app

# Celery  
docker-compose logs -f celery

# Database
docker-compose logs -f postgres
```

### Metrics
```bash
# Active tasks
celery -A workers.celery_app inspect active

# Task stats
celery -A workers.celery_app inspect stats
```

## 🚀 Deployment

### Development (Local Docker)
```bash
docker-compose up -d
```

### Production (VM with Systemd)
```bash
# See DEPLOYMENT.md for complete guide
# Includes: SSL, Nginx, PostgreSQL backup, monitoring
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

## 🧪 Test Coverage

Current test suite:
- ✅ 15 core LLM/workflow tests
- ✅ 8 API endpoint tests
- ✅ 4 Celery task tests
- ✅ 7 integration tests
- **Total: 27+ tests passing**

Run tests:
```bash
pytest tests/ -v --cov=app --cov=workers
```

## 🔐 Security

- ✅ API key validation (input)
- ✅ Database user permissions restricted
- ✅ CORS properly configured
- ✅ Rate limiting ready
- ✅ Environment variables not in git
- ✅ Password-protected Redis

Production:
- Configure HTTPS/TLS (Let's Encrypt)
- Enable API authentication
- Set up WAF rules
- Configure database encryption
- Regular security updates

## 💡 Example Usage

### Python

```python
import requests

# 1. Create a job
response = requests.post("http://localhost:8000/jobs", json={
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "job_post": "Build an e-commerce platform for fashion retailers",
    "source_platform": "web"
})
job_id = response.json()["job_id"]

# 2. Check job status (with WebSocket for real-time)
response = requests.get(f"http://localhost:8000/jobs/{job_id}")
status = response.json()["job"]["status"]

# 3. Submit user input
requests.patch(f"http://localhost:8000/jobs/{job_id}/answer", json={
    "answers": {
        "q1": "Fashion retailers",
        "q2": "Budget: $50k, Timeline: 3 months"
    }
})
```

### JavaScript

```javascript
// Real-time updates via WebSocket
const ws = new WebSocket(`ws://localhost:8000/ws/jobs/${jobId}`);
ws.onmessage = (event) => {
  console.log("Update:", JSON.parse(event.data));
};
```

## 📝 Project Structure

```
├── app/
│   ├── main.py              # FastAPI app
│   ├── db.py                # Database setup
│   ├── models/
│   │   ├── requests.py      # Pydantic validation
│   │   └── ui.py            # Response schemas
│   └── routes/
│       └── jobs.py          # Job endpoints
├── workers/
│   ├── celery_app.py        # Celery config
│   └── tasks.py             # Async tasks
├── agents/
│   ├── developer.py         # Code generation
│   ├── devops.py            # Infrastructure
│   └── reviewer.py          # Quality check
├── tests/
│   ├── test_job_flow.py     # Core tests
│   ├── test_integration.py  # E2E tests
│   └── conftest.py          # Fixtures
└── k8s/
    ├── deployment.yaml
    └── ...                  # K8s manifests
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Write tests for new functionality
4. Run test suite (`pytest tests/`)
5. Commit changes
6. Push to branch
7. Create Pull Request

## 📄 License

MIT License - See LICENSE file

## 🆘 Support & Troubleshooting

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Common issues and solutions
- Performance tuning
- Incident response
- Monitoring setup

## ✅ Completion Status

| Phase | Status | Tests |
|-------|--------|-------|
| 1-4: Core System | ✅ Complete | 15 tests |
| 5a: LLM Errors | ✅ Complete | 5 tests |
| 5b: Celery Errors | ✅ Complete | 4 tests |
| 5c: API Validation | ✅ Complete | 8 tests |
| 5d: DB Constraints | ✅ Complete | Migrations |
| 6: Integration | ✅ Complete | 7 tests |
| 6: Deployment | ✅ Complete | Docs |
| **Total** | **✅ PRODUCTION READY** | **27+ tests** |

## 🎯 Next Steps

- Deploy to production (follow [DEPLOYMENT.md](DEPLOYMENT.md))
- Set up monitoring (Prometheus, Grafana)
- Configure SSL/TLS
- Implement user authentication
- Add payment processing integration
- Scale Celery workers as needed

---

**Last Updated**: February 11, 2024  
**Version**: 1.0.0 (Production Ready)

4. DevOps setup

### Voorbeeld:
```bash
python main.py

> Beschrijf je project idee: Een todo-lijst API met FastAPI en SQLite

[Product Owner Agent analyseert...]
[Developer Agent schrijft code...]
[Reviewer Agent controleert...]
[DevOps Agent maakt deployment files...]
```

## 📁 Project Structuur

```
multi-agent-dev/
├── main.py              # Hoofdscript
├── agents/              # Agent definities
│   ├── product_owner.py
│   ├── developer.py
│   ├── reviewer.py
│   └── devops.py
├── orchestrator.py      # Workflow beheer
├── utils.py            # Helper functies
├── .env                # API key (NIET committen!)
├── .env.example        # Voorbeeld
├── requirements.txt    # Dependencies
└── output/             # Gegenereerde bestanden
```

## 🔧 Configuratie

Je kunt de agents aanpassen in `config.py`:
- Model selectie (haiku, sonnet, opus)
- Temperature settings
- Max tokens
- Agent prompts

## 📝 Volgende stappen

- [ ] Test met een simpel project
- [ ] Pas agent prompts aan naar jouw voorkeuren
- [ ] Voeg custom agents toe
- [ ] Migreer naar web-applicatie (Fase 3)

## 🤝 Contributing

Dit is jouw persoonlijke development tool - pas aan zoals je wilt!

## ⚖️ License

MIT
