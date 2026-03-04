"""Agents API endpoints."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


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
    return record



class AgentCreate(BaseModel):
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
            ORDER BY hired_at DESC
            """
        )

    result: List[Dict[str, Any]] = []
    for row in rows:
        result.append(_serialize_agent_row(row))
    return result


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


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreate) -> Dict[str, Any]:
    pool = await get_db()
    hired_at = body.hired_at or datetime.utcnow()
    updated_at = body.updated_at or datetime.utcnow()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO hired_agents (
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
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14, $15, $16
            )
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
            body.agent_id,
            body.name,
            body.role,
            body.specialization,
            body.status,
            _to_json_str(body.permissions),
            body.system_instructions,
            _to_json_str(body.knowledge_base_sources),
            _to_json_str(body.tool_access_whitelist),
            _to_json_str(body.hiring_logic),
            body.performance_score,
            body.completed_tasks,
            hired_at,
            updated_at,
            body.is_suspended,
            body.system_prompt,
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
