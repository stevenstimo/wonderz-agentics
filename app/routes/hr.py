"""HR Manager API endpoints."""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import app.db as _db
from app.services.hr_manager import HRManager

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
    point_id: str = Field(..., description="Development point to approve")
    source_url: str = Field(..., description="Training URL")
    approved_by: str = Field(default="ceo", description="Approver")


class ResolveRequest(BaseModel):
    resolution: str


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
