"""Agent management API routes.

CRUD for hired_agents table + training endpoints.
"""

import uuid
import json
import logging
from typing import Optional, List, Any
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

import app.db as _db
from app.services.training import run_training
from app.services.agent_validator import (
    validate_agent_config,
    generate_agent_id,
    AgentValidationError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, alias="agent_name")
    role: str
    system_instructions: str = Field(..., min_length=20, alias="system_prompt")
    tool_access_whitelist: Optional[List[str]] = Field(default_factory=list, alias="tool_whitelist")
    specialization: Optional[str] = None
    goal: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, alias="agent_name")
    system_instructions: Optional[str] = Field(default=None, alias="system_prompt")
    tool_access_whitelist: Optional[List[str]] = Field(default=None, alias="tool_whitelist")
    status: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    role: str
    specialization: str
    status: str
    system_instructions: str
    tool_access_whitelist: List[str]
    performance_score: float
    completed_tasks: int
    hired_at: str
    updated_at: str


def _parse_tool_whitelist(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value) or []
        except json.JSONDecodeError:
            return []
    return []


def _serialize_agent(row: Any) -> AgentResponse:
    data = dict(row)
    return AgentResponse(
        agent_id=data["agent_id"],
        name=data["name"],
        role=data["role"],
        specialization=data["specialization"],
        status=data["status"],
        system_instructions=data["system_instructions"],
        tool_access_whitelist=_parse_tool_whitelist(data.get("tool_access_whitelist")),
        performance_score=float(data.get("performance_score") or 0),
        completed_tasks=int(data.get("completed_tasks") or 0),
        hired_at=data["hired_at"].isoformat(),
        updated_at=data["updated_at"].isoformat(),
    )


@router.get("", response_model=List[AgentResponse])
async def list_agents(role: Optional[str] = None, status: Optional[str] = None):
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

        if status:
            query += f" AND status = ${idx}"
            params.append(status)
            idx += 1

        query += " ORDER BY hired_at DESC"
        rows = await conn.fetch(query, *params)

    return [_serialize_agent(r) for r in rows]


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(req: AgentCreateRequest):
    """Create a new hired agent."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    try:
        config = validate_agent_config(
            name=req.name,
            role=req.role,
            system_instructions=req.system_instructions,
            tool_access_whitelist=req.tool_access_whitelist,
            specialization=req.specialization,
        )
    except AgentValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    agent_id = generate_agent_id(config["name"], config["role"])

    async with pool.acquire() as conn:
        # Check for duplicate agent_id
        existing = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Agent with this name/role combination already exists: {agent_id}",
            )

        row = await conn.fetchrow(
            """
            INSERT INTO hired_agents (
                agent_id, name, role, specialization,
                system_instructions, tool_access_whitelist,
                status, performance_score, completed_tasks,
                hiring_logic
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            agent_id,
            config["name"],
            config["role"],
            config["specialization"],
            config["system_instructions"],
            json.dumps(config["tool_access_whitelist"]),
            "active",
            0.5,
            0,
            req.goal or "",
        )

    logger.info(f"Created agent {agent_id}: {config['name']} ({config['role']})")
    return _serialize_agent(row)


@router.get("/{agent_id}", response_model=AgentResponse)
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

    return _serialize_agent(row)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, req: AgentUpdateRequest):
    """Update agent fields."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )

    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")

    if (
        req.name is not None
        or req.system_instructions is not None
        or req.tool_access_whitelist is not None
    ):
        try:
            validate_agent_config(
                name=req.name or existing["name"],
                role=existing["role"],
                system_instructions=req.system_instructions or existing["system_instructions"],
                tool_access_whitelist=(
                    req.tool_access_whitelist
                    if req.tool_access_whitelist is not None
                    else _parse_tool_whitelist(existing.get("tool_access_whitelist"))
                ),
                specialization=existing.get("specialization"),
            )
        except AgentValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    updates = []
    params = [agent_id]
    idx = 2

    if req.name is not None:
        updates.append(f"name = ${idx}")
        params.append(req.name)
        idx += 1

    if req.status is not None:
        if req.status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Status must be active or inactive")
        updates.append(f"status = ${idx}")
        params.append(req.status)
        idx += 1

    if req.system_instructions is not None:
        updates.append(f"system_instructions = ${idx}")
        params.append(req.system_instructions)
        idx += 1

    if req.tool_access_whitelist is not None:
        updates.append(f"tool_access_whitelist = ${idx}")
        params.append(json.dumps(req.tool_access_whitelist))
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")

    query = f"""
        UPDATE hired_agents
        SET {', '.join(updates)}
        WHERE agent_id = $1
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    return _serialize_agent(row)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
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

    return None


# ============ Training Endpoints ============

class TrainAgentRequest(BaseModel):
    source_url: str


@router.post("/{agent_id}/train")
async def train_agent(agent_id: str, req: TrainAgentRequest, background_tasks: BackgroundTasks):
    """Start training an agent with a URL source."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    # Verify agent exists
    async with pool.acquire() as conn:
        agent = await conn.fetchrow(
            "SELECT agent_id, name FROM hired_agents WHERE agent_id = $1",
            agent_id
        )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        session_id = str(uuid.uuid4())

        await conn.execute("""
            INSERT INTO agent_training_sessions
            (session_id, agent_id, source_url, status)
            VALUES ($1, $2, $3, 'pending')
        """, session_id, agent_id, req.source_url)

    # Run training in background
    background_tasks.add_task(run_training, pool, session_id, agent_id, req.source_url)

    logger.info(f"Training started: agent={agent_id}, session={session_id}, url={req.source_url}")
    return {
        "session_id": session_id,
        "agent_id": agent_id,
        "status": "training_started",
        "source_url": req.source_url
    }


@router.get("/{agent_id}/training-sessions")
async def get_training_sessions(agent_id: str):
    """Get training history for an agent."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        sessions = await conn.fetch("""
            SELECT * FROM agent_training_sessions
            WHERE agent_id = $1
            ORDER BY started_at DESC
            LIMIT 20
        """, agent_id)

    return {
        "sessions": [
            {
                **dict(s),
                "id": str(s["id"]),
                "started_at": s["started_at"].isoformat() if s.get("started_at") else None,
                "completed_at": s["completed_at"].isoformat() if s.get("completed_at") else None,
            }
            for s in sessions
        ]
    }
