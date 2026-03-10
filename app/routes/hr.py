"""HR Manager API endpoints."""

import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Set, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.middleware.auth import require_super_admin
from pydantic import BaseModel, model_validator, Field, root_validator

from app.database import get_db
from app.services.hr_manager import HRManager
from app.agents.hr_manager import HRManager as SpecHRManager, _serialize as _serialize_spec
from app.orchestration.manager import OperationsManager
from models.unified import JobStatus, StrategicBrief
from app.services.training import train_agent_from_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr", tags=["hr"])

TRAINING_REQUESTS_UNAVAILABLE = {
    "error": "training_requests niet beschikbaar",
    "detail": "Tabel bestaat nog niet",
}


def _is_training_requests_unavailable(exc: Exception) -> bool:
    try:
        import asyncpg
        if type(exc).__name__ == "UndefinedTableError" or (
            hasattr(asyncpg, "UndefinedTableError") and isinstance(exc, asyncpg.UndefinedTableError)
        ):
            return "training_requests" in str(exc).lower()
    except Exception:
        pass
    msg = str(exc).lower()
    return "training_requests" in msg and ("does not exist" in msg or "undefined_table" in msg or "relation" in msg)
_columns_cache: Dict[str, Set[str]] = {}


async def _get_table_columns(conn, table_name: str) -> Set[str]:
    if table_name in _columns_cache:
        return _columns_cache[table_name]
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table_name,
    )
    cols = {r["column_name"] for r in rows}
    _columns_cache[table_name] = cols
    return cols


def _decision_timestamp_column(columns: Set[str], approved: bool) -> Optional[str]:
    if approved and "approved_at" in columns:
        return "approved_at"
    if not approved and "rejected_at" in columns:
        return "rejected_at"
    if "resolved_at" in columns:
        return "resolved_at"
    if "updated_at" in columns:
        return "updated_at"
    return None


def _decision_actor_column(columns: Set[str], approved: bool) -> Optional[str]:
    if approved and "approved_by" in columns:
        return "approved_by"
    if not approved and "rejected_by" in columns:
        return "rejected_by"
    if "resolved_by" in columns:
        return "resolved_by"
    if "approved_by" in columns:
        return "approved_by"
    return None


def _decision_notes_column(columns: Set[str]) -> Optional[str]:
    if "approval_notes" in columns:
        return "approval_notes"
    if "notes" in columns:
        return "notes"
    return None


class DevelopmentPoint(BaseModel):
    point_id: Any
    agent_id: Optional[Any] = None
    agent_role: Optional[str] = None
    issue_description: str
    frequency: int
    impact: str
    status: str
    source_url: Optional[str] = None
    evidence_example: Optional[str] = None
    proposed_by: Optional[str] = None
    resolution: Optional[str] = None
    approval_notes: Optional[str] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None


class ApproveTrainingRequest(BaseModel):
    # Development point approval (legacy path)
    point_id: Optional[Any] = Field(default=None, description="Development point to approve")
    # Training request approval (new path)
    request_id: Optional[Any] = Field(default=None, description="Training request to approve")
    approved: Optional[bool] = Field(default=None, description="Approve or reject training request")
    source_url: Optional[str] = Field(default=None, description="Training URL")
    notes: Optional[str] = Field(default=None, description="Approval notes")
    approved_by: str = Field(default="ceo", description="Approver")

    @model_validator(mode='after')
    def validate_payload(self):
        if self.request_id or self.approved is not None:
            if self.approved is None:
                raise ValueError("approved is required when approving training requests")
        elif not self.point_id:
            raise ValueError("point_id or request_id is required")
        return self

class ResolveRequest(BaseModel):
    resolution: str


class ResolveHiringRequest(BaseModel):
    agent_id: Any
    notes: Optional[str] = None


class HiringDecisionRequest(BaseModel):
    decided_by: str = Field(default="ceo", description="Approver/rejector")
    notes: Optional[str] = None


async def _get_hr_manager() -> HRManager:
    pool = await get_db()
    return HRManager(pool)


async def _get_spec_hr() -> SpecHRManager:
    pool = await get_db()
    return SpecHRManager(pool)


class UpdatePointBody(BaseModel):
    status: str
    approved_by: Optional[str] = None
    source_url: Optional[str] = None


@router.get("/improvements")
async def list_improvements():
    """List improvement suggestions (alias for development-points)."""
    hr = await _get_hr_manager()
    points = await hr.get_development_points(status="OPEN")
    return [{"id": p.get("point_id") or p.get("id"), "agent_id": p.get("agent_id"),
             "agent_role": p.get("agent_role"), "category": p.get("category"),
             "description": p.get("description"), "impact": p.get("impact"),
             "status": p.get("status"), "source_url": p.get("source_url"),
             "created_at": str(p.get("created_at", ""))} for p in points]


@router.get("/development-points")
async def list_development_points(
    agent_id: Optional[str] = Query(None),
    agent_role: Optional[str] = Query(None),
    impact: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    format: Optional[str] = Query(None, description="'spec' for {development_points, count}"),
):
    """Lists development points with optional filters. Default: spec format for HRDashboard."""
    if format == "legacy":
        # Legacy format: use services HRManager
        hr = await _get_hr_manager()
        status_filter = None
        if status:
            status_lower = (status or "").lower()
            if status_lower not in {"all", "any", "*"}:
                status_filter = status
        points = await hr.get_development_points(
            agent_id=agent_id,
            agent_role=agent_role,
            impact=impact,
            status=status_filter,
        )
        return [
            DevelopmentPoint(
                point_id=p.get("point_id") or p.get("id"),
                agent_id=p.get("agent_id"),
                agent_role=p.get("agent_role"),
                issue_description=p.get("issue_description") or p.get("description") or "",
                frequency=p.get("frequency") or 0,
                impact=p.get("impact") or "low",
                status=p.get("status") or "OPEN",
                source_url=p.get("source_url"),
                evidence_example=p.get("evidence_example"),
                proposed_by=p.get("proposed_by"),
                resolution=p.get("resolution"),
                approval_notes=p.get("approval_notes") or p.get("notes"),
                approved_by=p.get("approved_by"),
                rejected_by=p.get("rejected_by"),
                created_at=p.get("created_at"),
                updated_at=p.get("updated_at"),
                resolved_at=p.get("resolved_at"),
            )
            for p in points
        ]
    # Spec format: { development_points, count }
    hr = await _get_spec_hr()
    pool = await get_db()
    async with pool.acquire() as conn:
        conditions = ["1=1"]
        params: list = []
        idx = 1
        if agent_id:
            conditions.append(f"dp.agent_id = ${idx}")
            params.append(agent_id)
            idx += 1
        if impact:
            conditions.append(f"dp.impact = ${idx}")
            params.append(impact)
            idx += 1
        if status:
            conditions.append(f"dp.status = ${idx}")
            params.append(status)
            idx += 1
        rows = await conn.fetch(
            f"""
            SELECT dp.*, ha.name as agent_name FROM development_points dp
            LEFT JOIN hired_agents ha ON dp.agent_id = ha.agent_id
            WHERE {' AND '.join(conditions)}
            ORDER BY CASE dp.impact WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                     dp.frequency DESC, dp.created_at DESC
            """,
            *params,
        )
    serialized = _serialize_spec(rows)
    return {"development_points": serialized, "count": len(serialized)}


@router.get("/report")
async def get_weekly_report(_: None = Depends(require_super_admin)):
    """Weekly HR performance report per agent. Super admin only. Uses spec agent (agent_name from name)."""
    hr = await _get_spec_hr()
    report = await hr.generate_weekly_report()
    return report


@router.post("/scan-patterns")
async def scan_patterns():
    """Manually trigger retry pattern scan."""
    hr = await _get_hr_manager()
    try:
        result = await hr.process_retry_patterns()
        return result
    except Exception as e:
        logger.error("Pattern scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve-training")
async def approve_training(req: ApproveTrainingRequest):
    """Approve a development point and start training."""
    # Training request approval path
    if req.request_id or req.approved is not None:
        try:
            pool = await get_db()

            async with pool.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'training_requests'"
                )
                if not exists:
                    return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)

                request = await conn.fetchrow(
                    "SELECT * FROM training_requests WHERE request_id = $1",
                    req.request_id,
                )
                if not request:
                    raise HTTPException(status_code=404, detail="Request not found")

                new_status = "approved" if req.approved else "rejected"
                await conn.execute(
                    """
                    UPDATE training_requests
                    SET status = $1,
                        approved_at = NOW(),
                        approved_by = $2,
                        approval_notes = $3
                    WHERE request_id = $4
                    """,
                    new_status,
                    req.approved_by,
                    req.notes,
                    req.request_id,
                )

            if req.approved:
                url = req.source_url or request.get("suggested_url")
                if not url:
                    raise HTTPException(status_code=400, detail="No training URL provided")

                await train_agent_from_url(
                    pool=pool,
                    agent_id=request["agent_id"],
                    url=url,
                    approved_by=req.approved_by,
                )

            return {
                "request_id": req.request_id,
                "status": new_status,
                "training_started": bool(req.approved),
            }
        except HTTPException:
            raise
        except Exception as e:
            if _is_training_requests_unavailable(e):
                return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)
            raise

    # Development point approval path (legacy)
    hr = await _get_hr_manager()
    try:
        result = await hr.approve_training(
            point_id=req.point_id,
            source_url=req.source_url,
            approved_by=req.approved_by,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Training approval failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hiring-requests")
async def get_hiring_requests(status: Optional[str] = None):
    """Get pending hiring requests."""
    pool = await get_db()

    query = "SELECT * FROM hiring_requests"
    params = []
    if status:
        query += " WHERE status = $1"
        params.append(status)
    else:
        query += " WHERE status = 'pending'"

    query += " ORDER BY created_at DESC"

    async with pool.acquire() as conn:
        requests = await conn.fetch(query, *params)

    return {
        "hiring_requests": [dict(r) for r in requests],
        "count": len(requests),
    }


@router.get("/hiring-requests/{request_id}/progress")
async def get_hiring_progress(request_id: str):
    from datetime import datetime
    pool = await get_db()
    async with pool.acquire() as conn:
        req = await conn.fetchrow("SELECT * FROM hiring_requests WHERE request_id = $1", request_id)
        if not req:
            raise HTTPException(404)
        elapsed = (datetime.utcnow() - req["created_at"]).total_seconds() / 60
        return {
            "status": req["status"],
            "progress_percentage": min(100, int(elapsed)),
            "status_message": "Agent ready!" if req["status"] == "hired" else "Waiting",
        }


@router.post("/hiring-requests/{request_id}/approve")
async def approve_hiring_request(request_id: str, payload: HiringDecisionRequest):
    """Approve a hiring request and mark the job as awaiting hire."""
    pool = await get_db()

    async with pool.acquire() as conn:
        request = await conn.fetchrow(
            "SELECT * FROM hiring_requests WHERE request_id = $1",
            request_id,
        )
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        if request.get("status") not in (None, "pending", "awaiting_approval"):
            raise HTTPException(status_code=400, detail=f"Request already {request.get('status')}")

        columns = await _get_table_columns(conn, "hiring_requests")
        updates = {"status": "approved"}

        actor_col = _decision_actor_column(columns, approved=True)
        if actor_col:
            updates[actor_col] = payload.decided_by

        notes_col = _decision_notes_column(columns)
        if notes_col and payload.notes is not None:
            updates[notes_col] = payload.notes

        timestamp_col = _decision_timestamp_column(columns, approved=True)
        set_clauses = []
        values = []
        for col, val in updates.items():
            set_clauses.append(f"{col} = ${len(values) + 1}")
            values.append(val)
        if timestamp_col:
            set_clauses.append(f"{timestamp_col} = NOW()")

        values.append(request_id)
        await conn.execute(
            f"UPDATE hiring_requests SET {', '.join(set_clauses)} WHERE request_id = ${len(values)}",
            *values,
        )

        job_id = request.get("job_id")
        if job_id:
            await conn.execute(
                "UPDATE jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                JobStatus.AWAITING_HIRE.value,
                job_id,
            )

    return {"request_id": request_id, "status": "approved", "job_id": request.get("job_id")}


@router.post("/hiring-requests/{request_id}/reject")
async def reject_hiring_request(request_id: str, payload: HiringDecisionRequest):
    """Reject a hiring request and cancel the related job."""
    pool = await get_db()

    async with pool.acquire() as conn:
        request = await conn.fetchrow(
            "SELECT * FROM hiring_requests WHERE request_id = $1",
            request_id,
        )
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        if request.get("status") not in (None, "pending", "awaiting_approval"):
            raise HTTPException(status_code=400, detail=f"Request already {request.get('status')}")

        columns = await _get_table_columns(conn, "hiring_requests")
        updates = {"status": "rejected"}

        actor_col = _decision_actor_column(columns, approved=False)
        if actor_col:
            updates[actor_col] = payload.decided_by

        notes_col = _decision_notes_column(columns)
        if notes_col and payload.notes is not None:
            updates[notes_col] = payload.notes

        timestamp_col = _decision_timestamp_column(columns, approved=False)
        set_clauses = []
        values = []
        for col, val in updates.items():
            set_clauses.append(f"{col} = ${len(values) + 1}")
            values.append(val)
        if timestamp_col:
            set_clauses.append(f"{timestamp_col} = NOW()")

        values.append(request_id)
        await conn.execute(
            f"UPDATE hiring_requests SET {', '.join(set_clauses)} WHERE request_id = ${len(values)}",
            *values,
        )

        job_id = request.get("job_id")
        if job_id:
            await conn.execute(
                "UPDATE jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                JobStatus.CANCELLED.value,
                job_id,
            )

    return {"request_id": request_id, "status": "rejected", "job_id": request.get("job_id")}


@router.post("/hiring-requests/{request_id}/resolve")
async def resolve_hiring_request(request_id: str, payload: ResolveHiringRequest):
    """Resolve a hiring request and resume job planning if possible."""
    pool = await get_db()

    async with pool.acquire() as conn:
        agent = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE agent_id = $1",
            payload.agent_id,
        )
        if not agent:
            raise HTTPException(status_code=400, detail="Agent not found in hired_agents")

        request = await conn.fetchrow(
            "SELECT * FROM hiring_requests WHERE request_id = $1",
            request_id,
        )
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        await conn.execute(
            """
            UPDATE hiring_requests
            SET status = 'hired',
                hired_agent_id = $1,
                resolved_at = NOW(),
                notes = $2
            WHERE request_id = $3
            """,
            payload.agent_id,
            payload.notes,
            request_id,
        )

        job_id = request.get("job_id")
        if job_id:
            job = await conn.fetchrow("SELECT context FROM jobs WHERE id = $1", job_id)
            ctx = job.get("context") if job else None
            if isinstance(ctx, str):
                try:
                    ctx = json.loads(ctx)
                except Exception:
                    ctx = {}
            ctx = ctx or {}

            brief_data = ctx.get("brief")
            if brief_data:
                try:
                    brief = StrategicBrief.model_validate(brief_data)
                    def _dummy_runner(agent_name: str, input_data: dict) -> dict:
                        return {"status": "success", "summary": f"Ran {agent_name}"}
                    mgr = OperationsManager(agent_runner=_dummy_runner)
                    await mgr.generate_and_propose_plan(str(job_id), brief)
                    await conn.execute(
                        "UPDATE jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                        JobStatus.PLAN_PROPOSED.value,
                        job_id,
                    )
                except Exception as e:
                    logger.error("Failed to resume planning for job %s: %s", job_id, e)

    return {"status": "resolved", "request_id": request_id}


class TrainingRequestIn(BaseModel):
    agent_id: Any
    reason: str
    confidence_score: Optional[float] = None
    suggested_url: Optional[str] = None


class TrainingRequestOut(BaseModel):
    request_id: Any
    agent_id: Any
    reason: str
    confidence_score: Optional[float] = None
    suggested_url: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None


@router.post("/training-request")
async def submit_training_request(req: TrainingRequestIn):
    try:
        pool = await get_db()

        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'training_requests'"
            )
            if not exists:
                return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)

            request_id = f"TR-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

            await conn.execute(
                """
                INSERT INTO training_requests (
                    request_id, agent_id, reason,
                    confidence_score, suggested_url,
                    status, created_at
                ) VALUES ($1, $2, $3, $4, $5, 'pending', NOW())
                """,
                request_id,
                req.agent_id,
                req.reason,
                req.confidence_score,
                req.suggested_url,
            )

        return {
            "request_id": request_id,
            "status": "pending",
            "agent_id": req.agent_id,
        }
    except Exception as e:
        if _is_training_requests_unavailable(e):
            return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)
        raise


@router.get("/training-requests", response_model=List[TrainingRequestOut])
async def list_training_requests(status: Optional[str] = Query(default="pending")):
    try:
        pool = await get_db()

        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'training_requests'"
            )
            if not exists:
                return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)

            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM training_requests
                    WHERE status = $1
                    ORDER BY created_at DESC
                    """,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM training_requests
                    ORDER BY created_at DESC
                    """
                )

        results = []
        for r in rows:
            data = dict(r)
            for key in ("created_at", "approved_at"):
                if data.get(key):
                    data[key] = data[key].isoformat()
            results.append(TrainingRequestOut(**data))
        return results
    except Exception as e:
        if _is_training_requests_unavailable(e):
            return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)
        raise


@router.patch("/development-points/{point_id}")
async def update_development_point(point_id: str, body: UpdatePointBody):
    """Spec endpoint: update development point status."""
    valid = {"OPEN", "AWAITING_APPROVAL", "IN_TRAINING", "RESOLVED", "DISMISSED"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Ongeldige status. Kies uit: {valid}")
    hr = await _get_spec_hr()
    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT point_id FROM development_points WHERE point_id = $1", point_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Point {point_id} niet gevonden")
    return await hr.update_point_status(point_id, body.status, body.approved_by, body.source_url)


@router.post("/development-points/{point_id}/resolve")
async def resolve_point(point_id: str, req: ResolveRequest):
    """Mark a development point as resolved."""
    hr = await _get_hr_manager()
    success = await hr.resolve_point(point_id, req.resolution)
    if not success:
        raise HTTPException(status_code=404, detail="Development point not found")
    return {"point_id": point_id, "status": "RESOLVED"}


@router.post("/development-points/{point_id}/dismiss")
async def dismiss_point(point_id: str):
    """Dismiss a development point."""
    hr = await _get_hr_manager()
    success = await hr.dismiss_point(point_id)
    if not success:
        raise HTTPException(status_code=404, detail="Development point not found")
    return {"point_id": point_id, "status": "DISMISSED"}


@router.post("/scan")
async def trigger_scan(since_days: int = Query(default=7)):
    """Manually trigger an HR scan. Uses spec agent (retry_count, agent_id from job_steps) + direct_chat scan."""
    hr = await _get_spec_hr()
    try:
        job_results = await hr.scan_job_steps(since_days=since_days)
        chat_results = await hr.scan_direct_chats(since_days=since_days)
        results = job_results + chat_results
    except Exception as e:
        logger.error("HR scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    created = sum(1 for r in results if r.get("action") == "created")
    incremented = sum(1 for r in results if r.get("action") == "incremented")
    return {"scanned_days": since_days, "results": results, "created": created, "incremented": incremented}


@router.post("/check-effectiveness/{point_id}")
async def check_training_effectiveness(point_id: str):
    """
    Vergelijkt retry frequentie voor en na training voor een development point.
    """
    pool = await get_db()

    try:
        async with pool.acquire() as conn:
            point = await conn.fetchrow(
                "SELECT * FROM development_points WHERE id = $1",
                point_id,
            )
            if not point:
                raise HTTPException(
                    status_code=404,
                    detail=f"Development point {point_id} not found",
                )

            agent_id = point["agent_id"]
            issue = point["description"]
            baseline_at = point["created_at"]

            before_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM job_steps
                WHERE agent_id = $1
                AND (output_data::text ILIKE $2 OR input_data::text ILIKE $2)
                AND started_at < $3
                """,
                agent_id,
                f"%{issue}%",
                baseline_at,
            ) or 0

            after_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM job_steps
                WHERE agent_id = $1
                AND (output_data::text ILIKE $2 OR input_data::text ILIKE $2)
                AND started_at >= $3
                """,
                agent_id,
                f"%{issue}%",
                baseline_at,
            ) or 0

            resolved = after_count < before_count

            if resolved:
                await conn.execute(
                    """
                    UPDATE development_points
                    SET status = 'RESOLVED'
                    WHERE id = $1
                    """,
                    point_id,
                )
                new_status = "RESOLVED"
            else:
                new_status = point["status"]

        return {
            "point_id": point_id,
            "agent_id": agent_id,
            "before_count": before_count,
            "after_count": after_count,
            "resolved": resolved,
            "status": new_status,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
