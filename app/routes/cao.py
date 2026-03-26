"""CAO monitoring — crew performance dashboard (admin)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.middleware.auth import TokenPayload, require_admin_or_super_admin
from app.services.cao_service import get_cao_dashboard

router = APIRouter(prefix="/api/cao", tags=["cao"])


@router.get("/dashboard")
async def cao_dashboard(
    _user: Annotated[TokenPayload, Depends(require_admin_or_super_admin)],
    period_days: int = Query(default=30, ge=1, le=365),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_cao_dashboard(conn, period_days=period_days)
    return data
