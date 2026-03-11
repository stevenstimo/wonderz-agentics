import os

from dotenv import load_dotenv
load_dotenv()  # load .env before any app code uses os.getenv (e.g. SUPABASE_URL)
load_dotenv(".env.vm")  # exe.dev VM config (overrides .env)

# Load config early so GOOGLE_ADS_DEVELOPER_TOKEN etc. are available from systemd Environment
import app.core.config  # noqa: F401

import json
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uuid
import asyncio
from typing import Any, Optional

from app.db import init_db_pool, close_db_pool

# Import job flow routes
from app.routes.jobs import router as jobs_router, _job_for_response

# Celery task will be imported lazily to avoid starting worker at import time


class CreateJobRequest(BaseModel):
    user_id: Any = Field(...)
    job_post: str = Field(min_length=10)
    source_platform: Optional[str] = None


app = FastAPI(title="Multi-Agentic Crew - Orchestrator API")

# CORS: allow frontend (Vercel + local dev) to call API
_cors_origins = os.getenv("CORS_ORIGINS", "https://wonderz-agentics.vercel.app,https://wonderz-agentic.exe.xyz,http://localhost:3000,http://localhost:3001,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import register_routers
register_routers(app)


# Include job flow routes
app.include_router(jobs_router)


@app.on_event("startup")
async def on_startup():
    pool = await init_db_pool()
    if not os.getenv("SUPABASE_URL"):
        import logging
        logging.getLogger(__name__).warning(
            "SUPABASE_URL not set — /api/clients and other auth routes will return 503 'Auth not configured'. "
            "Set it in systemd Environment or .env (e.g. https://your-project.supabase.co)."
        )
    if pool:
        from app.services.scheduler import start_scheduler
        start_scheduler(pool)


@app.on_event("shutdown")
async def on_shutdown():
    from app.services.scheduler import stop_scheduler
    stop_scheduler()
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
                    "SELECT id, status, context, updated_at, job_number_int FROM jobs WHERE id=$1",
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
                        "job": _job_for_response(job_row),
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
    source_platform = req.source_platform or "custom"
    try:
        uuid.UUID(str(req.user_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format (must be UUID)")
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (
                id,
                user_id,
                job_post,
                status,
                source_platform,
                context,
                created_at,
                updated_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,now(),now())
            """,
            job_id,
            str(req.user_id),
            req.job_post,
            "INTAKE_CLARIFICATION",
            source_platform,
            json.dumps({"source_platform": source_platform}),
        )

    # Enqueue Celery task (lazy import to keep API lightweight)
    try:
        from workers.tasks import run_job
        # Use delay to enqueue; this returns immediately
        run_job.delay(job_id, None, {"job_post": req.job_post, "source_platform": source_platform})
    except Exception as e:
        # If task enqueue fails, mark job failed
        async with _pool.acquire() as conn:
            await conn.execute("UPDATE jobs SET status=$1 WHERE id=$2", "FAILED", job_id)
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {e}")

    return {"job_id": job_id, "status": "INTAKE_CLARIFICATION"}


@app.get("/api/legacy/jobs/{job_id}")
async def get_job_legacy(job_id: str):
    from app.db import _pool
    if _pool is None:
        raise HTTPException(status_code=500, detail="DB pool not initialized")

    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id,
                user_id,
                job_post,
                status,
                source_platform,
                context,
                created_at,
                updated_at,
                token_budget,
                tokens_used,
                token_limit_exceeded_at,
                token_used_total,
                job_number_int
            FROM jobs
            WHERE id=$1
            """,
            job_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_for_response(row)


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
        row = await conn.fetchrow("SELECT status, context FROM jobs WHERE id=$1", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        if row["status"] != "AWAITING_APPROVAL":
            raise HTTPException(status_code=409, detail="job is not awaiting approval")

        # mark running and enqueue worker
        await conn.execute("UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2", "RUNNING", job_id)

        # fetch context payload
        payload = row["context"] or {}

    try:
        from workers.tasks import run_job
        run_job.delay(job_id, None, payload or {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to re-enqueue job: {e}")

    return {"job_id": job_id, "status": "RUNNING"}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "ok": True}
