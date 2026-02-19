"""Agent management API routes.

CRUD for hired_agents table + training endpoints.
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

import app.db as _db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


class CreateAgentRequest(BaseModel):
    agent_name: str
    role: str
    specialization: Optional[str] = None
    goal: Optional[str] = None
    system_prompt: Optional[str] = None
    tool_whitelist: Optional[List[str]] = []


class UpdateAgentRequest(BaseModel):
    agent_name: Optional[str] = None
    role: Optional[str] = None
    specialization: Optional[str] = None
    status: Optional[str] = None
    system_prompt: Optional[str] = None
    tool_whitelist: Optional[List[str]] = None


@router.get("")
async def list_agents(role: str = None, status_filter: str = None):
    """List all hired agents, optionally filtered by role or status."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        query = "SELECT * FROM hired_agents WHERE 1=1"
        params = []
        idx = 1

        if role:
            query += f" AND role = ${idx}"
            params.append(role)
            idx += 1

        if status_filter:
            query += f" AND status = ${idx}"
            params.append(status_filter)
            idx += 1

        query += " ORDER BY performance_score DESC, name ASC"
        rows = await conn.fetch(query, *params)

    agents = []
    for r in rows:
        d = dict(r)
        # Serialize UUID and datetime fields
        d["id"] = str(d["id"])
        d["hired_at"] = d["hired_at"].isoformat() if d.get("hired_at") else None
        d["updated_at"] = d["updated_at"].isoformat() if d.get("updated_at") else None
        agents.append(d)

    return {"agents": agents, "total": len(agents)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(req: CreateAgentRequest):
    """Create a new hired agent."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    agent_id = f"agent:{req.role}:{uuid.uuid4().hex[:8]}"

    async with pool.acquire() as conn:
        # Check for duplicate role+name
        existing = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE name = $1 AND role = $2",
            req.agent_name, req.role
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Agent with name '{req.agent_name}' and role '{req.role}' already exists"
            )

        await conn.execute(
            """
            INSERT INTO hired_agents (
                agent_id, name, role, specialization, status,
                system_instructions, tool_access_whitelist,
                hiring_logic, hired_at, updated_at
            )
            VALUES ($1, $2, $3, $4, 'active', $5, $6, $7, NOW(), NOW())
            """,
            agent_id,
            req.agent_name,
            req.role,
            req.specialization or "",
            req.system_prompt or "",
            json.dumps(req.tool_whitelist or []),
            req.goal or ""
        )

    logger.info(f"Created agent {agent_id}: {req.agent_name} ({req.role})")
    return {
        "agent_id": agent_id,
        "name": req.agent_name,
        "role": req.role,
        "status": "active"
    }


@router.get("/{agent_id:path}")
async def get_agent(agent_id: str):
    """Get a single agent by agent_id."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM hired_agents WHERE agent_id = $1",
            agent_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    d = dict(row)
    d["id"] = str(d["id"])
    d["hired_at"] = d["hired_at"].isoformat() if d.get("hired_at") else None
    d["updated_at"] = d["updated_at"].isoformat() if d.get("updated_at") else None
    return d


@router.patch("/{agent_id:path}")
async def update_agent(agent_id: str, req: UpdateAgentRequest):
    """Update agent fields."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    updates = []
    params = []
    idx = 1

    if req.agent_name is not None:
        updates.append(f"name = ${idx}")
        params.append(req.agent_name)
        idx += 1

    if req.role is not None:
        updates.append(f"role = ${idx}")
        params.append(req.role)
        idx += 1

    if req.specialization is not None:
        updates.append(f"specialization = ${idx}")
        params.append(req.specialization)
        idx += 1

    if req.status is not None:
        updates.append(f"status = ${idx}")
        params.append(req.status)
        idx += 1

    if req.system_prompt is not None:
        updates.append(f"system_instructions = ${idx}")
        params.append(req.system_prompt)
        idx += 1

    if req.tool_whitelist is not None:
        updates.append(f"tool_access_whitelist = ${idx}")
        params.append(json.dumps(req.tool_whitelist))
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")
    params.append(agent_id)

    query = f"UPDATE hired_agents SET {', '.join(updates)} WHERE agent_id = ${idx}"

    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"agent_id": agent_id, "updated": True}


@router.delete("/{agent_id:path}")
async def deactivate_agent(agent_id: str):
    """Deactivate an agent (soft delete)."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE hired_agents SET status = 'inactive', updated_at = NOW() WHERE agent_id = $1",
            agent_id
        )

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"agent_id": agent_id, "status": "inactive"}
