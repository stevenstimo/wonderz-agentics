import os
import json
import logging
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uuid
import asyncio

# --- Structured logging (Taak 6) ---
from app.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

import app.db as _db
from app.db import init_db_pool, close_db_pool

# Import job flow routes
from app.routes.jobs import router as jobs_router
from app.routes.agents import router as agents_router
from app.routes.hr import router as hr_router
from app.routes.talents import router as talents_router
from app.routes.crew import router as crew_router
from app.routes.settings import router as settings_router
from app.routes.skills import router as skills_router
from app.routes import training
# from app.routes import admin

# Celery task will be imported lazily to avoid starting worker at import time


class CreateJobRequest(BaseModel):
    store_id: str | None = None
    job_type: str = "pdp_optimization"
    payload: dict | None = {}


app = FastAPI(title="Multi-Agentic Crew - Orchestrator API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://wonderz-agentic.exe.xyz",
        "https://wonderz-agentic.exe.xyz:3000",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(jobs_router)
app.include_router(agents_router)
app.include_router(hr_router)
app.include_router(talents_router)
app.include_router(crew_router)
app.include_router(settings_router)
app.include_router(skills_router)
app.include_router(training.router)
# app.include_router(admin.router)


# --- Worker circuit breaker endpoints (Taak 5) ---

@app.get("/api/worker/status")
async def worker_circuit_status():
    """Get circuit breaker status."""
    try:
        import redis as _r
        from app.services.circuit_breaker import CircuitBreaker
        r = _r.Redis(host="localhost", port=6379, db=0, socket_timeout=2)
        cb = CircuitBreaker(r)
        return cb.status()
    except Exception as e:
        return {"state": "unknown", "error": str(e)[:100]}


@app.post("/api/worker/reset")
async def reset_circuit_breaker():
    """Reset circuit breaker (admin)."""
    try:
        import redis as _r
        from app.services.circuit_breaker import CircuitBreaker
        r = _r.Redis(host="localhost", port=6379, db=0, socket_timeout=2)
        cb = CircuitBreaker(r)
        cb.reset()
        return {"status": "circuit_breaker_reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Training session progress (top-level to avoid agent path conflicts) ---

@app.get("/api/training-sessions/{session_id}")
async def get_training_progress(session_id: str):
    """Get training progress for a specific session."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")
    async with pool.acquire() as conn:
        session = await conn.fetchrow(
            "SELECT * FROM agent_training_sessions WHERE session_id = $1",
            session_id
        )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        **dict(session),
        "id": str(session["id"]),
        "started_at": session["started_at"].isoformat() if session.get("started_at") else None,
        "completed_at": session["completed_at"].isoformat() if session.get("completed_at") else None,
    }


# --- Stub endpoints for JobCenter compatibility ---

@app.get("/api/health")
async def health_check():
    """Extended health check — DB, Redis, disk. Returns 503 when degraded."""
    from datetime import datetime
    from fastapi.responses import JSONResponse
    import shutil

    health: dict = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
    }

    # 1. Database
    try:
        pool = _db._pool
        if pool:
            async with pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                health["checks"]["database"] = "ok" if result == 1 else "error"
        else:
            health["checks"]["database"] = "no_pool"
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["database"] = f"error: {str(e)[:80]}"
        health["status"] = "degraded"

    # 2. Redis
    try:
        import redis as _r
        r = _r.Redis(host="localhost", port=6379, db=0, socket_timeout=2)
        r.ping()
        health["checks"]["redis"] = "ok"
    except Exception as e:
        health["checks"]["redis"] = f"error: {str(e)[:80]}"
        health["status"] = "degraded"

    # 3. Disk space
    try:
        disk = shutil.disk_usage("/")
        pct = (disk.used / disk.total) * 100
        health["checks"]["disk_usage"] = f"{pct:.1f}%"
        if pct > 90:
            health["status"] = "degraded"
    except Exception:
        health["checks"]["disk_usage"] = "unknown"

    # Alert on degraded
    if health["status"] != "ok":
        try:
            from app.services.alerting import AlertManager
            AlertManager.get().send_alert(
                "Service Degraded",
                f"Health check failed: {health['checks']}",
                priority="high",
            )
        except Exception:
            pass

    code = 200 if health["status"] == "ok" else 503
    return JSONResponse(content=health, status_code=code)


# /api/crew is now served by app.routes.crew (database-backed)


@app.get("/api/explainer/sections")
async def get_explainer_sections():
    """Return platform status sections."""
    return {
        "sections": [
            {"title": "Agents Active", "value": 3, "detail": "CEO, Copy, Review"},
            {"title": "Jobs Today", "value": "—", "detail": "Check Job Center"},
        ],
        "meta": {"version": "1.0", "platform": "Wonderz Agentics"}
    }


# ----------- Scheduled tasks -----------
_hr_scan_task = None


@app.on_event("startup")
async def on_startup():
    await init_db_pool()

    # Schedule daily HR scan at 2:00 AM
    async def _daily_hr_scan():
        import asyncio
        while True:
            try:
                # Calculate seconds until next 2:00 AM
                from datetime import datetime, timedelta
                now = datetime.now()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                wait_seconds = (next_run - now).total_seconds()

                import logging
                logging.getLogger(__name__).info(
                    f"HR scan scheduled in {wait_seconds/3600:.1f}h (at {next_run.strftime('%H:%M')})"
                )
                await asyncio.sleep(wait_seconds)

                # Run the scan
                from app.services.hr_manager import HRManager
                pool = _db._pool if hasattr(_db, '_pool') else None
                if pool:
                    hr = HRManager(pool)
                    result = await hr.process_retry_patterns()
                    logging.getLogger(__name__).info(f"Daily HR scan completed: {result}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"HR scan error: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour

    global _hr_scan_task
    _hr_scan_task = asyncio.create_task(_daily_hr_scan())


@app.on_event("shutdown")
async def on_shutdown():
    global _hr_scan_task
    if _hr_scan_task:
        _hr_scan_task.cancel()
    await close_db_pool()


@app.websocket("/ws/jobs/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()

    from app.db import _pool
    if _pool is None:
        await websocket.close(code=1011)
        return

    last_job_updated_at = None
    last_steps_max_created_at = None

    try:
        while True:
            async with _pool.acquire() as conn:
                job_row = await conn.fetchrow(
                    "SELECT id, status, context, updated_at FROM jobs WHERE id=$1",
                    job_id
                )
                if not job_row:
                    await websocket.send_json({
                        "type": "error",
                        "message": "job not found"
                    })
                    await asyncio.sleep(1.5)
                    continue

                steps_max = await conn.fetchval(
                    "SELECT MAX(created_at) FROM job_steps WHERE job_id=$1",
                    job_id
                )

                should_push = False
                if job_row.get("updated_at") != last_job_updated_at:
                    should_push = True
                if steps_max != last_steps_max_created_at:
                    should_push = True

                if should_push:
                    steps = await conn.fetch(
                        "SELECT * FROM job_steps WHERE job_id=$1 ORDER BY step_index",
                        job_id
                    )
                    await websocket.send_json({
                        "type": "job_update",
                        "job": dict(job_row),
                        "steps": [dict(s) for s in steps]
                    })
                    last_job_updated_at = job_row.get("updated_at")
                    last_steps_max_created_at = steps_max

            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        return


@app.post("/api/legacy/jobs")
async def create_job_legacy(req: CreateJobRequest):
    # Minimal safe insertion using asyncpg pool via app.db
    from app.db import _pool

    if _pool is None:
        raise HTTPException(status_code=500, detail="DB pool not initialized")

    job_id = str(uuid.uuid4())
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO jobs(id, store_id, job_type, status, payload, created_at) VALUES($1,$2,$3,$4,$5,now())",
            job_id,
            req.store_id,
            req.job_type,
            "queued",
            json.dumps(req.payload or {}),
        )

    # Enqueue Celery task (lazy import to keep API lightweight)
    try:
        from workers.tasks import run_job
        # Use delay to enqueue; this returns immediately
        run_job.delay(job_id, req.store_id, req.payload or {})
    except Exception as e:
        # If task enqueue fails, mark job failed
        async with _pool.acquire() as conn:
            await conn.execute("UPDATE jobs SET status=$1 WHERE id=$2", "failed", job_id)
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {e}")

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/legacy/jobs/{job_id}")
async def get_job_legacy(job_id: str):
    from app.db import _pool
    if _pool is None:
        raise HTTPException(status_code=500, detail="DB pool not initialized")

    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, status, payload, result_summary, created_at, started_at, finished_at FROM jobs WHERE id=$1", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        return dict(row)


# -----------  Status / health summary  -----------
import subprocess, redis as _redis_lib

@app.get("/api/status/summary")
async def status_summary():
    """Live service health dashboard data."""
    import app.db as _db
    checks = {}

    # 1. Database
    try:
        pool = _db._pool
        if pool:
            async with pool.acquire() as conn:
                ver = await conn.fetchval("SELECT version()")
            checks["database"] = {"ok": True, "detail": "Connected", "version": ver[:60] if ver else ""}
        else:
            checks["database"] = {"ok": False, "detail": "Pool not initialized"}
    except Exception as e:
        checks["database"] = {"ok": False, "detail": str(e)[:120]}

    # 2. Redis
    try:
        r = _redis_lib.Redis(host="localhost", port=6379, socket_timeout=2)
        r.ping()
        checks["redis"] = {"ok": True, "detail": "PONG"}
    except Exception as e:
        checks["redis"] = {"ok": False, "detail": str(e)[:120]}

    # 3. Celery worker
    try:
        r = _redis_lib.Redis(host="localhost", port=6379, socket_timeout=2)
        # Check if any worker has registered
        from celery import Celery as _Celery
        _c = _Celery(broker="redis://localhost:6379/0")
        insp = _c.control.inspect(timeout=2)
        active = insp.active_queues() or {}
        if active:
            workers = list(active.keys())
            checks["celery_worker"] = {"ok": True, "detail": f"{len(workers)} worker(s): {', '.join(workers)}"}
        else:
            checks["celery_worker"] = {"ok": False, "detail": "No workers responding"}
    except Exception as e:
        checks["celery_worker"] = {"ok": False, "detail": str(e)[:120]}

    # 4. Frontend (vite on :3000)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://localhost:3000/")
            checks["frontend"] = {"ok": resp.status_code == 200, "detail": f"HTTP {resp.status_code}"}
    except Exception as e:
        checks["frontend"] = {"ok": False, "detail": str(e)[:120]}

    # 5. Backend (self)
    checks["backend"] = {"ok": True, "detail": "Running (this service)"}

    # 5b. Terminal (ttyd on 7681)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://localhost:7681/")
            checks["terminal"] = {"ok": resp.status_code == 200, "detail": f"HTTP {resp.status_code} (port 7681)"}
    except Exception as e:
        checks["terminal"] = {"ok": False, "detail": str(e)[:120]}

    # 5c. Codex Web (port 8080)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://localhost:8080/")
            checks["codex_web"] = {"ok": resp.status_code == 200, "detail": f"HTTP {resp.status_code} (port 8080)"}
    except Exception as e:
        checks["codex_web"] = {"ok": False, "detail": str(e)[:120]}

    # 6. Systemd service states
    services = {}
    for svc in ["wonderz-backend", "wonderz-worker", "wonderz-frontend", "redis-server", "wonderz-terminal", "wonderz-codex-web"]:
        try:
            result = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=3)
            state = result.stdout.strip()
            services[svc] = {"active": state == "active", "state": state}
        except Exception:
            services[svc] = {"active": False, "state": "unknown"}

    # 7. Recent git commits
    recent_commits = []
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            capture_output=True, text=True, timeout=5,
            cwd="/home/exedev/wonderz-agentics"
        )
        recent_commits = [l for l in result.stdout.strip().split("\n") if l]
    except Exception:
        pass

    # 8. LLM keys configured
    settings = {
        "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "active_providers": [p for p, v in [
            ("Anthropic", os.getenv("ANTHROPIC_API_KEY")),
            ("OpenAI", os.getenv("OPENAI_API_KEY")),
        ] if v],
        "ok": bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")),
    }

    all_ok = all(c["ok"] for c in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "health": {"status": "ok" if all_ok else "degraded", "checks": checks},
        "systemd": services,
        "settings": settings,
        "recent": {"recent_commits": recent_commits},
    }


from fastapi import Request


def _check_basic_auth_header(auth_header: str) -> None:
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized")
    import base64, os
    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "basic":
            raise HTTPException(status_code=401, detail="Unauthorized")
        decoded = base64.b64decode(token).decode()
        user, pwd = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    ok_user = os.getenv("APPROVAL_USER")
    ok_pass = os.getenv("APPROVAL_PASS")
    if not ok_user or not ok_pass or user != ok_user or pwd != ok_pass:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/api/legacy/jobs/{job_id}/approve")
async def approve_job_legacy(job_id: str, request: Request):
    """Approve a job that is in AWAITING_APPROVAL; transitions it back to 'queued' and re-enqueues the worker."""
    from app.db import _pool
    if _pool is None:
        raise HTTPException(status_code=500, detail="DB pool not initialized")

    from fastapi import Depends, HTTPException
    from fastapi.security import HTTPBasic, HTTPBasicCredentials
    security = HTTPBasic()

    creds: HTTPBasicCredentials = Depends(security)  # placeholder to satisfy typing; we will fetch below

    # Basic auth check
    from fastapi import Request
    # Manual header extraction because we want minimal deps and env-based user/pass
    # Read Authorization header
    async def _check_auth(request: Request):
        auth = request.headers.get("Authorization")
        if not auth:
            raise HTTPException(status_code=401, detail="Unauthorized")
        # Basic base64 check
        import base64
        try:
            scheme, token = auth.split(" ", 1)
            if scheme.lower() != "basic":
                raise HTTPException(status_code=401, detail="Unauthorized")
            decoded = base64.b64decode(token).decode()
            user, pwd = decoded.split(":", 1)
        except Exception:
            raise HTTPException(status_code=401, detail="Unauthorized")

        import os
        ok_user = os.getenv("APPROVAL_USER")
        ok_pass = os.getenv("APPROVAL_PASS")
        if not ok_user or not ok_pass or user != ok_user or pwd != ok_pass:
            raise HTTPException(status_code=403, detail="Forbidden")

    # Check basic auth header
    _check_basic_auth_header(request.headers.get("Authorization"))

    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status, store_id, payload FROM jobs WHERE id=$1", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        if row["status"] != "AWAITING_APPROVAL":
            raise HTTPException(status_code=409, detail="job is not awaiting approval")

        # mark running and enqueue worker
        await conn.execute("UPDATE jobs SET status=$1, started_at=now() WHERE id=$2", "running", job_id)

        # fetch payload and store_id
        store_id = row["store_id"]
        payload = row["payload"]

    try:
        from workers.tasks import run_job
        run_job.delay(job_id, store_id, payload or {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to re-enqueue job: {e}")

    return {"job_id": job_id, "status": "running"}
