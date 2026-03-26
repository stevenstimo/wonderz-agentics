"""
FastAPI app — main backend entry point.

Run: uvicorn app.main:app --host 0.0.0.0 --port 8090
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import init_db_pool, close_db_pool
from app.logging_config import setup_logging

from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings

_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
setup_logging(_log_level)

logger = logging.getLogger(__name__)


async def recover_stuck_jobs(db_pool) -> None:
    """
    Safety guard: mark RUNNING jobs older than timeout as FAILED.

    This prevents the UI from showing jobs forever when the worker is down or
    the backend crashed while a job was in-flight.
    """

    try:
        async with db_pool.acquire() as conn:
            stuck_jobs = await conn.fetch(
                """
                SELECT id, updated_at
                FROM jobs
                WHERE status = 'RUNNING'
                  AND updated_at < now() - interval '60 minutes'
                """
            )
            if not stuck_jobs:
                return

            error_detail = "Backend herstart — job kon niet worden hervat."
            payload_update = {"error_reason": error_detail}
            payload_json = json.dumps(payload_update)

            for row in stuck_jobs:
                await conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'FAILED',
                        updated_at = now(),
                        payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb
                    WHERE id = $2
                    """,
                    payload_json,
                    row["id"],
                )
    except Exception:
        logger.exception("Failed to run stuck job recovery on startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool, then start EmailPoller if Gmail credentials set. Shutdown: close pool."""
    pool = await init_db_pool()
    if pool:
        app.state.db_pool = pool
        await recover_stuck_jobs(pool)
        from app.services.system_events_service import SystemEventsService, set_global_instance
        app.state.system_events = SystemEventsService(pool)
        set_global_instance(app.state.system_events)

    # ARQ pool for persistent background job processing.
    try:
        redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))
        app.state.arq_pool = await arq_create_pool(redis_settings)
        logger.info("ARQ pool initialised")
    except Exception as e:
        app.state.arq_pool = None
        logger.exception("Failed to initialise ARQ pool: %s", e)

    gmail_address = (os.getenv("GMAIL_ADDRESS") or "").strip()
    app_password = (os.getenv("GMAIL_APP_PASSWORD") or "").strip()
    if gmail_address and app_password:
        from app.services.email_poller import EmailPoller
        poller = EmailPoller(gmail_address=gmail_address, app_password=app_password)
        asyncio.create_task(poller.poll_loop())
        logger.info("EmailPoller started (Gmail intake)")
    else:
        logger.warning(
            "EmailPoller not started: GMAIL_ADDRESS or GMAIL_APP_PASSWORD missing in env. "
            "Set both in .env to enable email intake."
        )

    # HR Manager dagelijkse scan
    async def hr_scan_loop():
        while True:
            try:
                from app.database import get_db
                from app.agents.hr_manager import HRManager
                pool = await get_db()
                hr = HRManager(pool)
                await hr.scan_job_steps(since_days=7)
                await hr.scan_job_performance()
                logger.info("HR scan voltooid")
            except Exception as e:
                logger.error("HR scan fout: %s", e, exc_info=True)
            await asyncio.sleep(86400)  # 24 uur

    asyncio.create_task(hr_scan_loop())
    logger.info("HR scan loop gestart")

    yield
    # Close ARQ pool first, so background enqueue can fail fast after shutdown.
    if getattr(app.state, "arq_pool", None):
        try:
            await app.state.arq_pool.aclose()
        except Exception:
            logger.exception("Failed to close ARQ pool")
    await close_db_pool()


app = FastAPI(
    title="Multi-Agentic Crew - Orchestrator API",
    lifespan=lifespan,
)

CORS_ORIGINS = [
    o.strip() for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3001,https://wonderz-agentic.exe.xyz,https://wonderz-agentics.vercel.app",
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return JSON on any unhandled exception so frontend can show a message instead of crashing on HTML."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# --- Routers (each defines its own prefix, e.g. /api/clients) ---
from app.routes import (
    agents,
    agent_inbox,
    auth,
    clients,
    dashboard,
    users,
    debug_chat,
    email as email_routes,
    email_inbox,
    ceo,
    cao,
    cfo,
    clo,
    crew,
    events,
    explainer,
    graph,
    google_integrations,
    hr,
    integrations,
    intelligence,
    jobs,
    knowledge as knowledge_routes,
    lessons,
    monitoring,
    newbies,
    settings,
    status,
    system_events as system_events_routes,
    talents,
    training,
    gtm,
    seo_upload,
    alex_dev,
    admin,
    skills,
    skill_registry,
    skill_factory,
    evals,
)

app.include_router(agents.router)
app.include_router(agent_inbox.router)
app.include_router(email_inbox.router)
app.include_router(clients.router)
app.include_router(debug_chat.router)
app.include_router(email_routes.router)
app.include_router(ceo.router)
app.include_router(cao.router)
app.include_router(cfo.router)
app.include_router(clo.router)
app.include_router(crew.router)
app.include_router(events.router)
app.include_router(explainer.router)
app.include_router(graph.router)
app.include_router(hr.router)
app.include_router(dashboard.router)
app.include_router(google_integrations.router)
app.include_router(integrations.router)
app.include_router(intelligence.router)
app.include_router(jobs.router)
app.include_router(knowledge_routes.router)
app.include_router(lessons.router)
app.include_router(monitoring.router)
app.include_router(newbies.router)
app.include_router(settings.router)
app.include_router(status.router)
app.include_router(system_events_routes.router)
app.include_router(talents.router)
app.include_router(training.router)
app.include_router(gtm.router)
app.include_router(seo_upload.router)
app.include_router(alex_dev.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(skills.router)
app.include_router(skill_registry.router)
app.include_router(skill_factory.router)
app.include_router(evals.router)


@app.get("/api/health")
async def health():
    """Lightweight health for proxies and UI."""
    return {"status": "ok", "service": "backend"}
