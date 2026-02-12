import os
import json
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uuid
import asyncio

from app.db import init_db_pool, close_db_pool

# Import job flow routes
from app.routes.jobs import router as jobs_router

# Celery task will be imported lazily to avoid starting worker at import time


class CreateJobRequest(BaseModel):
    store_id: str | None = None
    job_type: str = "pdp_optimization"
    payload: dict | None = {}


app = FastAPI(title="Multi-Agentic Crew - Orchestrator API")


# Include job flow routes
app.include_router(jobs_router)


@app.on_event("startup")
async def on_startup():
    await init_db_pool()


@app.on_event("shutdown")
async def on_shutdown():
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

