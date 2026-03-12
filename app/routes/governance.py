"""Platform Spec V7 — Governance Monitoring API."""
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Query

from pydantic import BaseModel

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.governance_monitor import GovernanceMonitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance"])


class ReleaseBody(BaseModel):
    approved_by: str


@router.post(
    "/run-check",
    dependencies=[Depends(get_current_user)],
)
async def run_governance_check(pool=Depends(get_db)) -> dict[str, Any]:
    """Trigger governance check. Returns breaches_found, agents_suspended, tasks_blocked, duration_ms."""
    if not pool:
        return {"breaches_found": 0, "agents_suspended": 0, "tasks_blocked": 0, "duration_ms": 0}
    start = time.perf_counter()
    result = await GovernanceMonitor().check_talent_integrity(pool)
    duration_ms = int((time.perf_counter() - start) * 1000)
    result["duration_ms"] = duration_ms
    return result


@router.get(
    "/metrics",
    dependencies=[Depends(get_current_user)],
)
async def get_governance_metrics(pool=Depends(get_db)) -> dict[str, Any]:
    """Talent governance metrics from talent_governance_metrics view."""
    if not pool:
        return {"agents": []}
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch("SELECT * FROM talent_governance_metrics")
        except Exception:
            return {"agents": []}
        agents = [
            {
                "talent_agent_id": r.get("talent_agent_id"),
                "total_reviews": r.get("total_reviews"),
                "approval_rate": float(r["approval_rate"]) if r.get("approval_rate") is not None else None,
                "evidence_verification_rate": float(r["evidence_verification_rate"]) if r.get("evidence_verification_rate") is not None else None,
                "monitoring_status": r.get("monitoring_status"),
            }
            for r in rows
        ]
    return {"agents": agents}


@router.get(
    "/suspended",
    dependencies=[Depends(get_current_user)],
)
async def get_suspended_agents(pool=Depends(get_db)) -> list[dict[str, Any]]:
    """Lijst van gesuspendeerde agents."""
    if not pool:
        return []
    return await GovernanceMonitor().get_suspended_agents(pool)


@router.post(
    "/release/{agent_id}",
    dependencies=[Depends(get_current_user)],
)
async def release_suspension(agent_id: str, body: ReleaseBody, pool=Depends(get_db)) -> dict[str, Any]:
    """Handmatige vrijgave van suspension. Body: { \"approved_by\": str }."""
    if not pool:
        return {"released": False, "agent_id": agent_id}
    released = await GovernanceMonitor().release_suspension(pool, agent_id, body.approved_by)
    return {"released": released, "agent_id": agent_id}


@router.get(
    "/breaches",
    dependencies=[Depends(get_current_user)],
)
async def get_breaches(
    pool=Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Recente governance breaches."""
    if not pool:
        return []
    return await GovernanceMonitor().get_breach_history(pool, limit=limit)
