"""HR Manager API endpoints."""

import logging
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, model_validator, Field, root_validator

import app.db as _db
from app.services.hr_manager import HRManager
from app.orchestration.manager import OperationsManager
from models.unified import JobStatus, StrategicBrief
from app.services.training import train_agent_from_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr", tags=["hr"])


class DevelopmentPoint(BaseModel):
    point_id: str
    agent_id: Optional[str] = None
    agent_role: Optional[str] = None
    issue_description: str
    frequency: int
    impact: str
    status: str
    source_url: Optional[str] = None
    created_at: Optional[str] = None


class ApproveTrainingRequest(BaseModel):
    # Development point approval (legacy path)
    point_id: Optional[str] = Field(default=None, description="Development point to approve")
    # Training request approval (new path)
    request_id: Optional[str] = Field(default=None, description="Training request to approve")
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
    agent_id: str
    notes: Optional[str] = None


async def _get_hr_manager() -> HRManager:
    pool = await _db.init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")
    return HRManager(pool)


@router.get("/development-points", response_model=List[DevelopmentPoint])
async def list_development_points(
    agent_id: Optional[str] = None,
    agent_role: Optional[str] = None,
    impact: Optional[str] = None,
    status: Optional[str] = None,
):
    """Lists development points with optional filters."""
    hr = await _get_hr_manager()
    points = await hr.get_development_points(
        agent_id=agent_id,
        agent_role=agent_role,
        impact=impact,
        status=status or "OPEN",
    )
    return [
        DevelopmentPoint(
            point_id=p.get("point_id"),
            agent_id=p.get("agent_id"),
            agent_role=p.get("agent_role"),
            issue_description=p.get("issue_description"),
            frequency=p.get("frequency"),
            impact=p.get("impact"),
            status=p.get("status"),
            source_url=p.get("source_url"),
            created_at=p.get("created_at"),
        )
        for p in points
    ]


@router.get("/report")
async def get_weekly_report():
    """Weekly HR performance report per agent."""
    hr = await _get_hr_manager()
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
        pool = await _db.init_db_pool()
        if not pool:
            raise HTTPException(status_code=503, detail="DB pool not initialised")

        async with pool.acquire() as conn:
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
    pool = await _db.init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

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


@router.post("/hiring-requests/{request_id}/resolve")
async def resolve_hiring_request(request_id: str, payload: ResolveHiringRequest):
    """Resolve a hiring request and resume job planning if possible."""
    pool = await _db.init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

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
    agent_id: str
    reason: str
    confidence_score: Optional[float] = None
    suggested_url: Optional[str] = None


class TrainingRequestOut(BaseModel):
    request_id: str
    agent_id: str
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
    pool = await _db.init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    request_id = f"TR-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    async with pool.acquire() as conn:
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


@router.get("/training-requests", response_model=List[TrainingRequestOut])
async def list_training_requests(status: Optional[str] = Query(default="pending")):
    pool = await _db.init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
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
    """Manually trigger an HR scan (for testing)."""
    hr = await _get_hr_manager()
    result = await hr.scan_job_steps(since_days=since_days)
    return {"status": "scan_completed", **result}
