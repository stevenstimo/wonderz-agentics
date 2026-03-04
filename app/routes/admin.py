"""
Temporary admin endpoints for maintenance tasks.
"""
import logging

from fastapi import APIRouter, HTTPException

from app.db import init_db_pool

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)


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
