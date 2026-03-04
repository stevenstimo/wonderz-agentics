"""CEO approval endpoints."""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

import app.db as _db
from app.services.hr_manager import HRManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ceo", tags=["ceo"])


async def _get_hr_manager() -> HRManager:
    pool = await _db.init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")
    return HRManager(pool)


def _point_to_approval(point: Dict[str, Any]) -> Dict[str, Any]:
    point_id = point.get("point_id") or point.get("id")
    return {
        "id": point_id,
        "point_id": point_id,
        "request_type": "training",
        "status": "pending",
        "raw_status": point.get("status"),
        "details": {
            "agent": point.get("agent_role") or point.get("agent_id"),
            "url": point.get("source_url") or point.get("suggested_url"),
            "issue": point.get("issue_description") or point.get("description"),
            "impact": point.get("impact"),
            "frequency": point.get("frequency"),
        },
        "requested_at": point.get("created_at"),
    }


@router.get("/approvals", response_model=List[Dict[str, Any]])
async def list_approvals():
    """Return development points awaiting CEO approval."""
    hr = await _get_hr_manager()
    points = await hr.get_development_points(status="AWAITING_APPROVAL")
    return [_point_to_approval(p) for p in points]
