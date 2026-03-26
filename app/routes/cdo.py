"""CDO monitoring — delivery / alignment dashboard (admin)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.middleware.auth import TokenPayload, require_admin_or_super_admin
from app.services.cdo_service import get_cdo_dashboard

router = APIRouter(prefix="/api/cdo", tags=["cdo"])


@router.get("/dashboard")
async def cdo_dashboard(
    _user: Annotated[TokenPayload, Depends(require_admin_or_super_admin)],
    period_days: int = Query(default=30, ge=1, le=365),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        data = await get_cdo_dashboard(conn, period_days=period_days)
    return data
