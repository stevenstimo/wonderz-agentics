"""
Temporary admin endpoints for maintenance tasks.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import init_db_pool
from app.middleware.auth import TokenPayload, require_super_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)


class PromoteCredentialsRequest(BaseModel):
    client_slug: str = Field(..., min_length=1)
    integration_type: str = Field(..., min_length=1)
    user_id: str | None = Field(
        default=None,
        description="Optional: promote only this user's row; otherwise newest user-owned row.",
    )


@router.post("/credentials/promote")
async def promote_credentials_to_platform(
    body: PromoteCredentialsRequest,
    _current_user: TokenPayload = Depends(require_super_admin),
):
    """Promoveer een user-owned koppeling naar platform-owned (super_admin only)."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    from app.services.credential_resolver import mark_as_platform_owned

    async with pool.acquire() as conn:
        ok = await mark_as_platform_owned(
            conn,
            body.client_slug.strip(),
            body.integration_type.strip(),
            user_id=body.user_id.strip() if body.user_id else None,
        )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Geen actieve user-owned koppeling gevonden voor deze client + integration.",
        )
    return {
        "status": "promoted",
        "client_slug": body.client_slug,
        "integration_type": body.integration_type,
    }


@router.post("/fix-knowledge-sources")
async def fix_knowledge_sources():
    """
    Patches NULL knowledge_base_sources to empty JSON array.

    This fixes the training status endpoint which expects
    knowledge_base_sources to be a valid JSON array.
    """
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        null_count = await conn.fetchval(
            "SELECT COUNT(*) FROM hired_agents WHERE knowledge_base_sources IS NULL"
        )

        logger.info("Found %s agents with NULL knowledge_base_sources", null_count)

        await conn.execute(
            """
            UPDATE hired_agents
            SET knowledge_base_sources = '[]'::jsonb
            WHERE knowledge_base_sources IS NULL
            """
        )

        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM hired_agents WHERE knowledge_base_sources IS NULL"
        )

        logger.info("Fixed %s agents, %s NULL values remain", null_count, remaining)

        return {
            "status": "success",
            "agents_fixed": null_count,
            "remaining_nulls": remaining,
        }
