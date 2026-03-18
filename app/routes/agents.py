"""Agents API — hired_agents lookup for UI (e.g. CEO name on New Job page)."""

import logging
from fastapi import APIRouter

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/ceo")
async def get_ceo_agent():
    """
    Return the CEO orchestrator from hired_agents (role = 'CEO', is_active).
    Used by frontend for dynamic UI labels (e.g. New Job page). Fallback in UI: "your AI agent".
    """
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT agent_id, name
            FROM hired_agents
            WHERE LOWER(TRIM(role)) = 'ceo' AND is_active = true
            LIMIT 1
            """
        )
    if not row:
        return {"agent_id": None, "name": None}
    return {"agent_id": row["agent_id"], "name": row["name"]}
