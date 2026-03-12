"""
FastAPI app — main backend entry point.

Run: uvicorn app.main:app --host 0.0.0.0 --port 8090
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db_pool, close_db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool. Shutdown: close pool."""
    await init_db_pool()
    yield
    await close_db_pool()


app = FastAPI(
    title="Multi-Agentic Crew - Orchestrator API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://wonderz-agentic.exe.xyz"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers (each defines its own prefix, e.g. /api/clients) ---
from app.routes import (
    agents,
    agent_inbox,
    auth,
    clients,
    ceo,
    crew,
    events,
    explainer,
    graph,
    hr,
    integrations,
    intelligence,
    jobs,
    knowledge as knowledge_routes,
    lessons,
    monitoring,
    settings,
    status,
    talents,
    training,
    gtm,
    seo_upload,
    alex_dev,
    admin,
    skills,
)

app.include_router(agents.router)
app.include_router(agent_inbox.router)
app.include_router(clients.router)
app.include_router(ceo.router)
app.include_router(crew.router)
app.include_router(events.router)
app.include_router(explainer.router)
app.include_router(graph.router)
app.include_router(hr.router)
app.include_router(integrations.router)
app.include_router(intelligence.router)
app.include_router(jobs.router)
app.include_router(knowledge_routes.router)
app.include_router(lessons.router)
app.include_router(monitoring.router)
app.include_router(settings.router)
app.include_router(status.router)
app.include_router(talents.router)
app.include_router(training.router)
app.include_router(gtm.router)
app.include_router(seo_upload.router)
app.include_router(alex_dev.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(skills.router)


@app.get("/api/health")
async def health():
    """Lightweight health for proxies and UI."""
    return {"status": "ok", "service": "backend"}
