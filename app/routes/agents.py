import os
import re
import json
import asyncpg
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix='/api/agents', tags=['agents'])


class CreateAgentRequest(BaseModel):
    agent_name: str
    role: str
    goal: str
    system_prompt: str
    tool_whitelist: Optional[List[str]] = Field(default_factory=list)


class UpdateAgentRequest(BaseModel):
    system_prompt: Optional[str] = None
    goal: Optional[str] = None
    tool_whitelist: Optional[List[str]] = None


def _agents_db_url() -> Optional[str]:
    # Assumption-based: agent lifecycle/training can use a dedicated vector-capable DB.
    # Fallback points to local Supabase Postgres when AGENTS_DATABASE_URL is not explicitly set.
    return (
        os.getenv('AGENTS_DATABASE_URL')
        or os.getenv('DATABASE_URL')
        or 'postgresql://postgres:postgres@localhost:54322/postgres'
    )


async def _connect() -> asyncpg.Connection:
    dsn = _agents_db_url()
    if not dsn:
        raise HTTPException(status_code=500, detail='Agent database URL not configured')
    try:
        return await asyncpg.connect(dsn)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Agent database unavailable: {exc}')


def _normalize_agent_id(role: str) -> str:
    role_slug = re.sub(r'[^a-z0-9]+', '-', role.strip().lower()).strip('-') or 'custom'
    return f'agent:{role_slug}'


def _to_json_compat(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


@router.get('')
async def list_agents():
    conn = await _connect()
    try:
        rows = await conn.fetch(
            '''
            SELECT agent_id, agent_name, role, goal, created_at
            FROM hired_agents
            WHERE is_active = true
            ORDER BY created_at DESC
            '''
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


@router.get('/{agent_id}')
async def get_agent(agent_id: str):
    conn = await _connect()
    try:
        row = await conn.fetchrow('SELECT * FROM hired_agents WHERE agent_id = $1', agent_id)
        if not row:
            raise HTTPException(status_code=404, detail='Agent not found')

        knowledge_chunks_count = await conn.fetchval(
            'SELECT COUNT(*) FROM agent_knowledge WHERE agent_id = $1 AND is_active = true',
            agent_id,
        )

        result = dict(row)
        result['tool_whitelist'] = _to_json_compat(result.get('tool_whitelist')) or []
        result['knowledge_sources'] = _to_json_compat(result.get('knowledge_sources')) or []
        result['knowledge_sources_count'] = len(result['knowledge_sources'])
        result['knowledge_chunks_count'] = knowledge_chunks_count
        return result
    finally:
        await conn.close()


@router.post('')
async def create_agent(req: CreateAgentRequest):
    conn = await _connect()
    try:
        if not req.agent_name.strip() or not req.role.strip() or not req.goal.strip() or not req.system_prompt.strip():
            raise HTTPException(status_code=422, detail='agent_name, role, goal, system_prompt are required')

        agent_id = _normalize_agent_id(req.role)

        existing = await conn.fetchrow('SELECT agent_id FROM hired_agents WHERE agent_id = $1', agent_id)
        if existing:
            # Assumption-based: duplicate role reactivates/overwrites same canonical agent_id entry.
            await conn.execute(
                '''
                UPDATE hired_agents
                SET agent_name = $2,
                    goal = $3,
                    system_prompt = $4,
                    tool_whitelist = $5::jsonb,
                    is_active = true
                WHERE agent_id = $1
                ''',
                agent_id,
                req.agent_name.strip(),
                req.goal.strip(),
                req.system_prompt.strip(),
                json.dumps(req.tool_whitelist or []),
            )
        else:
            await conn.execute(
                '''
                INSERT INTO hired_agents (
                    agent_id, agent_name, role, goal, system_prompt,
                    tool_whitelist, knowledge_sources, is_active, created_at
                )
                VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,true,now())
                ''',
                agent_id,
                req.agent_name.strip(),
                req.role.strip(),
                req.goal.strip(),
                req.system_prompt.strip(),
                json.dumps(req.tool_whitelist or []),
                json.dumps([]),
            )

        row = await conn.fetchrow('SELECT * FROM hired_agents WHERE agent_id = $1', agent_id)
        result = dict(row)
        result['tool_whitelist'] = _to_json_compat(result.get('tool_whitelist')) or []
        result['knowledge_sources'] = _to_json_compat(result.get('knowledge_sources')) or []
        return result
    finally:
        await conn.close()


@router.patch('/{agent_id}')
async def update_agent(agent_id: str, req: UpdateAgentRequest):
    conn = await _connect()
    try:
        existing = await conn.fetchrow('SELECT * FROM hired_agents WHERE agent_id = $1', agent_id)
        if not existing:
            raise HTTPException(status_code=404, detail='Agent not found')

        updates = []
        values = []

        if req.system_prompt is not None:
            updates.append(f'system_prompt = ${len(values) + 2}')
            values.append(req.system_prompt.strip())
        if req.goal is not None:
            updates.append(f'goal = ${len(values) + 2}')
            values.append(req.goal.strip())
        if req.tool_whitelist is not None:
            updates.append(f'tool_whitelist = ${len(values) + 2}::jsonb')
            values.append(json.dumps(req.tool_whitelist))

        if not updates:
            raise HTTPException(status_code=400, detail='No updatable fields provided')

        sql = 'UPDATE hired_agents SET ' + ', '.join(updates) + f' WHERE agent_id = $1 RETURNING *'
        row = await conn.fetchrow(sql, agent_id, *values)

        result = dict(row)
        result['tool_whitelist'] = _to_json_compat(result.get('tool_whitelist')) or []
        result['knowledge_sources'] = _to_json_compat(result.get('knowledge_sources')) or []
        return result
    finally:
        await conn.close()


@router.delete('/{agent_id}')
async def deactivate_agent(agent_id: str):
    conn = await _connect()
    try:
        row = await conn.fetchrow('SELECT agent_id, is_active FROM hired_agents WHERE agent_id = $1', agent_id)
        if not row:
            raise HTTPException(status_code=404, detail='Agent not found')

        await conn.execute('UPDATE hired_agents SET is_active = false WHERE agent_id = $1', agent_id)
        return {'agent_id': agent_id, 'status': 'deactivated'}
    finally:
        await conn.close()
