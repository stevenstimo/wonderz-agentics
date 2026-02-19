"""HR Manager API routes.

Endpoints for development points, weekly reports, and manual scans.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import app.db as _db
from app.services.hr_manager import HRManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr", tags=["hr"])


class ResolveRequest(BaseModel):
    resolution: str


def _get_hr_manager() -> HRManager:
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")
    return HRManager(pool)


@router.get("/development-points")
async def list_development_points(
    agent_role: Optional[str] = None,
    impact: Optional[str] = None,
    status: str = Query(default="OPEN")
):
    """List development points, optionally filtered."""
    hr = _get_hr_manager()
    points = await hr.get_development_points(
        agent_role=agent_role,
        impact=impact,
        status=status
    )
    return {"development_points": points, "total": len(points)}


@router.get("/report")
async def get_weekly_report():
    """Weekly HR performance report per agent."""
    hr = _get_hr_manager()
    report = await hr.generate_weekly_report()
    return report


@router.post("/development-points/{point_id}/resolve")
async def resolve_point(point_id: str, req: ResolveRequest):
    """Mark a development point as resolved."""
    hr = _get_hr_manager()
    success = await hr.resolve_point(point_id, req.resolution)
    if not success:
        raise HTTPException(status_code=404, detail="Development point not found")
    return {"point_id": point_id, "status": "RESOLVED"}


@router.post("/development-points/{point_id}/dismiss")
async def dismiss_point(point_id: str):
    """Dismiss a development point."""
    hr = _get_hr_manager()
    success = await hr.dismiss_point(point_id)
    if not success:
        raise HTTPException(status_code=404, detail="Development point not found")
    return {"point_id": point_id, "status": "DISMISSED"}


@router.post("/scan")
async def trigger_scan(since_days: int = Query(default=7)):
    """Manually trigger an HR scan (for testing)."""
    hr = _get_hr_manager()
    result = await hr.scan_job_steps(since_days=since_days)
    return {"status": "scan_completed", **result}
