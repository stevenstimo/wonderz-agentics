"""COO monitoring — production / RUNNING pipeline dashboard (admin)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.middleware.auth import TokenPayload, require_admin_or_super_admin
from app.services.coo_service import get_coo_dashboard

router = APIRouter(prefix="/api/coo", tags=["coo"])


@router.get("/dashboard")
async def coo_dashboard(
    _user: Annotated[TokenPayload, Depends(require_admin_or_super_admin)],
    period_days: int = Query(default=30, ge=1, le=365),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_coo_dashboard(conn, period_days=period_days)
    return data
