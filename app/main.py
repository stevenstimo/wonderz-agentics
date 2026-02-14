import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
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


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _runtime_overview_payload() -> dict:
    root = _workspace_root()
    run_dir = root / "crew" / "reports" / "runs"
    agents_dir = root / "crew" / "agents"
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)

    run_files = sorted(run_dir.glob("run-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:250]
    total_runs = 0
    total_success = 0
    total_failed = 0
    last_24h_runs = 0
    last_24h_success = 0
    failure_types: dict[str, int] = {}
    intent_counts: dict[str, int] = {}
    playbook_counts: dict[str, int] = {}
    governance_blocked = 0
    retries_total = 0
    lessons_used_total = 0
    llm_used_runs = 0
    token_total = 0
    step_total = 0
    step_latency_ms_total = 0
    ambiguity_count = 0
    runs_with_failures = 0
    run_durations_ms: list[int] = []
    recent_runs: list[dict] = []
    latest_run_ts = None

    for file_path in run_files:
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        summary = None
        run_completed_ts = None
        run_started_ts = None
        run_ambiguous = False
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "run_started":
                run_started_ts = _safe_parse_iso_utc(event.get("ts"))
            if event.get("type") == "intent_classified" and bool(event.get("ambiguous")):
                run_ambiguous = True
            if event.get("type") == "run_completed":
                summary = event.get("summary") or {}
                run_completed_ts = _safe_parse_iso_utc(event.get("ts"))
                break

        if not summary:
            continue

        total_runs += 1
        status = summary.get("status")
        if status == "success":
            total_success += 1
        else:
            total_failed += 1

        retries_total += int(summary.get("retry_count") or 0)
        lessons_used_total += int(summary.get("lessons_used") or 0)
        if run_ambiguous:
            ambiguity_count += 1

        intent = summary.get("intent")
        if intent:
            intent_counts[intent] = intent_counts.get(intent, 0) + 1

        playbook = summary.get("playbook")
        if playbook:
            playbook_counts[playbook] = playbook_counts.get(playbook, 0) + 1

        metrics = summary.get("metrics") or {}
        llm_usage = metrics.get("llm_usage") or {}
        step_total += int(metrics.get("step_count") or 0)
        step_latency_ms_total += int(metrics.get("total_step_latency_ms") or 0)
        token_total += int(llm_usage.get("total_tokens") or 0)
        llm = summary.get("llm") or {}
        if bool(llm.get("used")):
            llm_used_runs += 1

        run_failures = summary.get("failures") or []
        if run_failures:
            runs_with_failures += 1
        for failure in summary.get("failures") or []:
            failure_type = failure.get("type") or "unknown"
            failure_types[failure_type] = failure_types.get(failure_type, 0) + 1
            if failure_type == "governance_blocked":
                governance_blocked += 1

        duration_ms = None
        if run_started_ts and run_completed_ts:
            duration_ms = int((run_completed_ts - run_started_ts).total_seconds() * 1000)
            if duration_ms >= 0:
                run_durations_ms.append(duration_ms)

        if run_completed_ts:
            if latest_run_ts is None or run_completed_ts > latest_run_ts:
                latest_run_ts = run_completed_ts
            if run_completed_ts >= since_24h:
                last_24h_runs += 1
                if status == "success":
                    last_24h_success += 1
            recent_runs.append({
                "run_id": summary.get("run_id"),
                "intent": intent,
                "playbook": playbook,
                "status": status,
                "retry_count": int(summary.get("retry_count") or 0),
                "failures": [f.get("type") or "unknown" for f in run_failures],
                "total_score": (summary.get("evaluation") or {}).get("total_score"),
                "duration_ms": duration_ms,
                "completed_at": run_completed_ts.isoformat(),
            })

    agent_profiles = sorted([p.name for p in agents_dir.glob("*.profile.yml")])
    top_failures = sorted(failure_types.items(), key=lambda item: item[1], reverse=True)[:5]
    top_intents = sorted(intent_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    top_playbooks = sorted(playbook_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    recent_runs = sorted(recent_runs, key=lambda row: row.get("completed_at") or "", reverse=True)[:10]
    avg_duration_ms = int(sum(run_durations_ms) / len(run_durations_ms)) if run_durations_ms else 0
    avg_step_latency_ms = int(step_latency_ms_total / step_total) if step_total else 0

    return {
        "status": "ok",
        "generated_at": now.isoformat(),
        "summary": {
            "total_runs": total_runs,
            "success_rate": (total_success / total_runs) if total_runs else 0.0,
            "failed_runs": total_failed,
            "last_24h_runs": last_24h_runs,
            "last_24h_success_rate": (last_24h_success / last_24h_runs) if last_24h_runs else 0.0,
            "latest_run_at": latest_run_ts.isoformat() if latest_run_ts else None,
        },
        "decision_quality": {
            "ambiguity_rate": (ambiguity_count / total_runs) if total_runs else 0.0,
            "avg_retries_per_run": (retries_total / total_runs) if total_runs else 0.0,
            "top_intents": [{"intent": k, "count": v} for k, v in top_intents],
            "top_playbooks": [{"playbook": k, "count": v} for k, v in top_playbooks],
        },
        "execution_quality": {
            "avg_step_latency_ms": avg_step_latency_ms,
            "avg_run_duration_ms": avg_duration_ms,
            "failure_run_rate": (runs_with_failures / total_runs) if total_runs else 0.0,
        },
        "learning_memory": {
            "avg_lessons_used_per_run": (lessons_used_total / total_runs) if total_runs else 0.0,
            "agents_with_profiles": len(agent_profiles),
        },
        "governance_safety": {
            "governance_blocked_events": governance_blocked,
        },
        "cost_performance": {
            "total_tokens": token_total,
            "avg_tokens_per_run": (token_total / total_runs) if total_runs else 0.0,
            "llm_usage_rate": (llm_used_runs / total_runs) if total_runs else 0.0,
        },
        "brains_map": {
            "orchestrator": "crew/scripts/lib/orchestrator.rb",
            "decision_engine": "crew/scripts/lib/decision_engine.rb",
            "execution_engine": "crew/scripts/lib/execution_engine.rb",
            "evaluator": "crew/scripts/lib/evaluator.rb",
            "memory_manager": "crew/scripts/lib/memory_manager.rb",
            "governance": "crew/scripts/lib/governance.rb",
            "llm_client": "crew/scripts/lib/llm_client.rb",
            "runtime_docs": "crew/docs/runtime_architecture.md",
        },
        "agents": agent_profiles,
        "top_failure_types": [{"type": k, "count": v} for k, v in top_failures],
        "top_intents": [{"intent": k, "count": v} for k, v in top_intents],
        "recent_runs": recent_runs,
    }


@app.get("/api/intelligence/overview")
async def intelligence_overview():
    return _runtime_overview_payload()


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
