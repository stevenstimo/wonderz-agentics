"""Agents API — hired_agents lookup for UI (e.g. CEO name on New Job page)."""

import logging

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

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


@router.get("")
async def get_agents(status: Optional[str] = Query(None)):
    """Return all hired agents, optionally filtered by is_active."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if status == "active":
            rows = await conn.fetch(
                """
                SELECT agent_id, name, role, category, is_active, is_suspended,
                       performance_score, completed_tasks, readiness_score,
                       model, temperature, created_at
                FROM hired_agents
                WHERE is_active = true
                ORDER BY created_at DESC
                """
            )
        elif status == "inactive":
            rows = await conn.fetch(
                """
                SELECT agent_id, name, role, category, is_active, is_suspended,
                       performance_score, completed_tasks, readiness_score,
                       model, temperature, created_at
                FROM hired_agents
                WHERE is_active = false
                ORDER BY created_at DESC
                """
            )
        else:
            rows = await conn.fetch(
                """
                SELECT agent_id, name, role, category, is_active, is_suspended,
                       performance_score, completed_tasks, readiness_score,
                       model, temperature, created_at
                FROM hired_agents
                ORDER BY created_at DESC
                """
            )

    agents = [dict(r) for r in rows]
    return {"agents": agents, "count": len(agents)}
