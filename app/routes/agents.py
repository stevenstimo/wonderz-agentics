"""Agents API endpoints."""

import json
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body

from app.middleware.auth import require_super_admin
from pydantic import BaseModel, Field

from app.database import get_db

# Hiring Hall spec: geldige tools en categorieën
VALID_TOOLS = [
    "read_product", "write_copy", "read_analytics", "write_social",
    "read_tickets", "write_tickets", "read_jobs", "send_report",
    "web_search", "read_lessons",
]
VALID_CATEGORIES = [
    "Management", "Content", "Marketing", "Operations",
    "Technical", "Support", "Analytics", "Custom",
]


def _json_default(obj: Any) -> Any:
    """For json.dumps: handle non-JSON-serializable values (e.g. datetime)."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"], dependencies=[Depends(require_super_admin)])


def _to_json_compat(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _to_json_str(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def _serialize_agent_row(row: Any) -> Dict[str, Any]:
    record = dict(row)
    record["permissions"] = _to_json_compat(record.get("permissions"))
    record["knowledge_base_sources"] = _to_json_compat(record.get("knowledge_base_sources"))
    record["tool_access_whitelist"] = _to_json_compat(record.get("tool_access_whitelist"))
    record["hiring_logic"] = _to_json_compat(record.get("hiring_logic"))
    # Spec compat: agent_name alias voor name
    if "name" in record and "agent_name" not in record:
        record["agent_name"] = record["name"]
    return record



def _generate_agent_id(role: str) -> str:
    """Genereert agent_id conform Product Spec: agent:<role>-<short-uuid>."""
    short_uuid = str(uuid.uuid4())[:4]
    safe_role = role.lower().replace(" ", "-")[:30]
    return f"agent:{safe_role}-{short_uuid}"


class KnowledgeSource(BaseModel):
    url: str
    added_at: Optional[str] = None
    status: str = "pending"
    approved_by: Optional[str] = None


class AgentCreateHiringHall(BaseModel):
    """Hiring Hall spec (Product Spec v1.1): agent_name, goal, system_prompt, etc."""
    agent_name: str = Field(..., min_length=2, max_length=100)
    role: str = Field(...)
    category: str = Field(default="Custom")
    goal: str = Field(..., min_length=10, max_length=500)
    system_prompt: str = Field(..., min_length=20)
    tool_whitelist: List[str] = Field(default_factory=list)
    knowledge_sources: List[Any] = Field(default_factory=list)


class AgentCreate(BaseModel):
    """Legacy: agent_id, name, role — backward compat voor talents promote etc."""
    agent_id: Any
    name: str
    role: str
    specialization: Optional[str] = None
    status: Optional[str] = None
    permissions: Optional[Any] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[Any] = None
    tool_access_whitelist: Optional[Any] = None
    hiring_logic: Optional[Any] = None
    performance_score: Optional[float] = None
    completed_tasks: Optional[int] = None
    hired_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_suspended: Optional[bool] = None
    system_prompt: Optional[str] = None


class AgentUpdate(BaseModel):
    agent_id: Optional[Any] = None
    name: Optional[str] = None
    role: Optional[str] = None
    specialization: Optional[str] = None
    status: Optional[str] = None
    permissions: Optional[Any] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[Any] = None
    tool_access_whitelist: Optional[Any] = None
    hiring_logic: Optional[Any] = None
    performance_score: Optional[float] = None
    completed_tasks: Optional[int] = None
    hired_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_suspended: Optional[bool] = None
    system_prompt: Optional[str] = None


class AgentResponse(BaseModel):
    id: Any
    agent_id: Any
    name: str
    role: str
    specialization: Optional[str] = None
    status: Optional[str] = None
    permissions: Optional[Any] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[Any] = None
    tool_access_whitelist: Optional[Any] = None
    hiring_logic: Optional[Any] = None
    performance_score: Optional[float] = None
    completed_tasks: Optional[int] = None
    hired_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_suspended: Optional[bool] = None
    system_prompt: Optional[str] = None


@router.get("", response_model=List[AgentResponse])
async def list_agents() -> List[Dict[str, Any]]:
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                agent_id,
                name,
                role,
                specialization,
                status,
                permissions,
                system_instructions,
                knowledge_base_sources,
                tool_access_whitelist,
                hiring_logic,
                performance_score,
                completed_tasks,
                hired_at,
                updated_at,
                is_suspended,
                system_prompt
            FROM hired_agents
            ORDER BY
                CASE WHEN LOWER(role) = 'ceo' THEN 0 ELSE 1 END,
                COALESCE(name, '') ASC
            """
        )

    result: List[Dict[str, Any]] = []
    for row in rows:
        result.append(_serialize_agent_row(row))
    return result


@router.get("/{agent_id}/detail")
async def get_agent_detail(agent_id: str) -> Dict[str, Any]:
    """Get agent plus related data: recent work, development points, applicable skills."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM hired_agents WHERE agent_id = $1", agent_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        agent = _serialize_agent_row(row)
        role = agent.get("role") or ""
        specialization = agent.get("specialization") or ""

        steps = await conn.fetch(
            """SELECT js.*, j.job_post FROM job_steps js
               LEFT JOIN jobs j ON js.job_id = j.id
               WHERE js.agent_role = $1
               ORDER BY js.created_at DESC NULLS LAST
               LIMIT 20""",
            role,
        )
        dev_points = await conn.fetch(
            """SELECT * FROM development_points
               WHERE agent_id = $1 OR agent_role = $2
               ORDER BY created_at DESC NULLS LAST
               LIMIT 20""",
            agent_id,
            role,
        )
        skills = await conn.fetch(
            """SELECT * FROM agent_skills
               WHERE $1 = ANY(applicable_to) OR $2 = ANY(applicable_to)""",
            role,
            specialization,
        )

    def row_to_dict(r) -> Dict[str, Any]:
        d = dict(r)
        for key in list(d.keys()):
            if hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat()
        return d

    return {
        "agent": agent,
        "recent_work": [row_to_dict(s) for s in steps],
        "development_points": [row_to_dict(d) for d in dev_points],
        "skills": [row_to_dict(s) for s in skills],
    }


@router.patch("/{agent_id}/avatar")
async def update_agent_avatar(agent_id: str, req: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Store avatar config in permissions.avatar."""
    pool = await get_db()
    merge = {"avatar": req}
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE hired_agents
               SET permissions = COALESCE(permissions, '{}'::jsonb) || $1::jsonb,
                   updated_at = now()
               WHERE agent_id = $2""",
            json.dumps(merge, default=_json_default),
            agent_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "updated"}


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str) -> Dict[str, Any]:
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id,
                agent_id,
                name,
                role,
                specialization,
                status,
                permissions,
                system_instructions,
                knowledge_base_sources,
                tool_access_whitelist,
                hiring_logic,
                performance_score,
                completed_tasks,
                hired_at,
                updated_at,
                is_suspended,
                system_prompt
            FROM hired_agents
            WHERE agent_id = $1
            """,
            agent_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    return _serialize_agent_row(row)


def _is_hiring_hall_payload(body: Dict[str, Any]) -> bool:
    """Detecteert spec-style payload (agent_name, goal) vs legacy (agent_id, name)."""
    return "agent_name" in body or "goal" in body


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Maakt een nieuwe agent aan.
    Ondersteunt twee payload-vormen:
    - Hiring Hall spec: agent_name, role, category, goal, system_prompt, tool_whitelist, knowledge_sources
    - Legacy: agent_id, name, role, specialization, system_instructions, etc.
    """
    pool = await get_db()
    now = datetime.now(timezone.utc)

    if _is_hiring_hall_payload(body):
        # ─── Hiring Hall spec (Product Spec v1.1) ─────────────────────────
        try:
            payload = AgentCreateHiringHall(**body)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

        # Valideer tool_whitelist
        for t in payload.tool_whitelist:
            if t not in VALID_TOOLS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Onbekende tool: {t}. Geldige tools: {VALID_TOOLS}",
                )

        agent_id = _generate_agent_id(payload.role)
        knowledge_json = json.dumps(payload.knowledge_sources) if payload.knowledge_sources else "[]"
        tool_json = json.dumps(payload.tool_whitelist)

        async with pool.acquire() as conn:
            # Check duplicate naam
            existing = await conn.fetchrow(
                "SELECT agent_id FROM hired_agents WHERE name = $1",
                payload.agent_name,
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Een actieve agent met de naam '{payload.agent_name}' bestaat al (ID: {existing['agent_id']}).",
                )

            row = await conn.fetchrow(
                """
                INSERT INTO hired_agents (
                    agent_id, name, role, goal, category,
                    system_prompt, system_instructions,
                    tool_access_whitelist, knowledge_base_sources,
                    status, is_active, is_suspended,
                    hired_at, updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $6,
                    $7::jsonb, $8::jsonb,
                    'active', true, false,
                    $9, $9
                )
                RETURNING *
                """,
                agent_id,
                payload.agent_name,
                payload.role,
                payload.goal,
                payload.category,
                payload.system_prompt,
                tool_json,
                knowledge_json,
                now,
            )

        logger.info("Agent aangemaakt (Hiring Hall): %s (%s)", agent_id, payload.agent_name)
        return _serialize_agent_row(row)

    # ─── Legacy payload (agent_id, name, role) ─────────────────────────────
    try:
        legacy = AgentCreate(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    hired_at = legacy.hired_at or now
    updated_at = legacy.updated_at or now

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO hired_agents (
                agent_id, name, role, specialization, status,
                permissions, system_instructions, knowledge_base_sources,
                tool_access_whitelist, hiring_logic,
                performance_score, completed_tasks, hired_at, updated_at,
                is_suspended, system_prompt
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16
            )
            RETURNING *
            """,
            legacy.agent_id,
            legacy.name,
            legacy.role,
            legacy.specialization,
            legacy.status or "active",
            _to_json_str(legacy.permissions),
            legacy.system_instructions,
            _to_json_str(legacy.knowledge_base_sources),
            _to_json_str(legacy.tool_access_whitelist),
            _to_json_str(legacy.hiring_logic),
            legacy.performance_score,
            legacy.completed_tasks,
            hired_at,
            updated_at,
            legacy.is_suspended,
            legacy.system_prompt,
        )

    return _serialize_agent_row(row)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, body: AgentUpdate) -> Dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    data["updated_at"] = datetime.utcnow()

    json_fields = {
        "permissions",
        "knowledge_base_sources",
        "tool_access_whitelist",
        "hiring_logic",
    }
    for key in json_fields:
        if key in data:
            data[key] = _to_json_str(data[key])

    columns = list(data.keys())
    set_clause = ", ".join(f"{col} = ${idx}" for idx, col in enumerate(columns, start=1))
    values = [data[col] for col in columns]
    values.append(agent_id)

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE hired_agents
            SET {set_clause}
            WHERE agent_id = ${len(values)}
            RETURNING
                id,
                agent_id,
                name,
                role,
                specialization,
                status,
                permissions,
                system_instructions,
                knowledge_base_sources,
                tool_access_whitelist,
                hiring_logic,
                performance_score,
                completed_tasks,
                hired_at,
                updated_at,
                is_suspended,
                system_prompt
            """,
            *values,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    return _serialize_agent_row(row)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str) -> Dict[str, Any]:
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            DELETE FROM hired_agents
            WHERE agent_id = $1
            RETURNING
                id,
                agent_id,
                name,
                role,
                specialization,
                status,
                permissions,
                system_instructions,
                knowledge_base_sources,
                tool_access_whitelist,
                hiring_logic,
                performance_score,
                completed_tasks,
                hired_at,
                updated_at,
                is_suspended,
                system_prompt
            """,
            agent_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"status": "deleted", "agent_id": agent_id}
