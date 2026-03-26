"""CLO monitoring — learning & development dashboard (admin)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.middleware.auth import TokenPayload, require_admin_or_super_admin
from app.services.clo_service import get_agent_learning_profile, get_clo_dashboard

router = APIRouter(prefix="/api/clo", tags=["clo"])


@router.get("/dashboard")
async def clo_dashboard(
    _user: Annotated[TokenPayload, Depends(require_admin_or_super_admin)],
    period_days: int = Query(default=30, ge=1, le=365),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_clo_dashboard(conn, period_days=period_days)
    return data


@router.get("/agents/{agent_id}/profile")
async def agent_learning_profile(
    agent_id: str,
    _user: Annotated[TokenPayload, Depends(require_admin_or_super_admin)],
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_agent_learning_profile(conn, agent_id)
    return data
