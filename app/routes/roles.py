from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("")
async def list_role_presets(
    agent_type: Optional[str] = Query(default=None),
    _: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """List active role presets, optionally filtered by agent_type."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if agent_type:
            rows = await conn.fetch(
                """
                SELECT role_id, role_label, agent_type, description, tool_whitelist,
                       output_format, guardrails, model_config, suggested_personas,
                       is_active, created_at
                FROM agent_role_presets
                WHERE is_active = true AND agent_type = $1
                ORDER BY agent_type, role_label
                """,
                agent_type,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT role_id, role_label, agent_type, description, tool_whitelist,
                       output_format, guardrails, model_config, suggested_personas,
                       is_active, created_at
                FROM agent_role_presets
                WHERE is_active = true
                ORDER BY agent_type, role_label
                """
            )
    return {"roles": [dict(r) for r in rows]}


@router.get("/{role_id}")
async def get_role_preset(
    role_id: str,
    _: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get one role preset by role_id."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT role_id, role_label, agent_type, description, tool_whitelist,
                   output_format, guardrails, model_config, suggested_personas,
                   is_active, created_at
            FROM agent_role_presets
            WHERE role_id = $1
            """,
            role_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Role preset '{role_id}' not found")
    return dict(row)
