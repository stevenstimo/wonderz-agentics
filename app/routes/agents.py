import os
import re
import json
import math
import hashlib
import asyncpg
from typing import List, Optional
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, BackgroundTasks
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


class TrainAgentRequest(BaseModel):
    source_url: str


EMBEDDING_DIM = 1536


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


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    return ' '.join(soup.get_text(separator=' ').split())


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = (text or '').split()
    if not words:
        return []
    step = max(1, chunk_size - overlap)
    chunks = []
    for idx in range(0, len(words), step):
        chunk_words = words[idx:idx + chunk_size]
        if chunk_words:
            chunks.append(' '.join(chunk_words))
    return chunks


def _embedding_to_pgvector(embedding: List[float]) -> str:
    clipped = embedding[:EMBEDDING_DIM]
    if len(clipped) < EMBEDDING_DIM:
        clipped += [0.0] * (EMBEDDING_DIM - len(clipped))
    return '[' + ','.join(f'{float(v):.8f}' for v in clipped) + ']'


def _fallback_embedding(text: str) -> List[float]:
    # Assumption-based: token-hash embedding fallback approximates lexical similarity
    # when OpenAI embeddings are unavailable in local dev.
    tokens = re.findall(r'[a-z0-9]+', (text or '').lower())
    if not tokens:
        tokens = ['empty']
    values = [0.0] * EMBEDDING_DIM
    for token in tokens:
        digest = hashlib.sha256(token.encode('utf-8')).digest()
        for offset in range(0, 16, 2):
            idx = ((digest[offset] << 8) | digest[offset + 1]) % EMBEDDING_DIM
            sign = 1.0 if digest[(offset + 2) % len(digest)] % 2 == 0 else -1.0
            values[idx] += sign
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


async def _embed_text(text: str) -> List[float]:
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    model = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small').strip()
    if not api_key:
        return _fallback_embedding(text)
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        response = await client.embeddings.create(model=model, input=text)
        embedding = response.data[0].embedding if response and response.data else None
        if embedding:
            return [float(v) for v in embedding]
    except Exception:
        pass
    return _fallback_embedding(text)


async def _run_training(agent_id: str, url: str):
    conn = await _connect()
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        text = _extract_text_from_html(html)
        chunks = _chunk_text(text, chunk_size=500, overlap=50)
        if not chunks:
            return

        for chunk_index, chunk in enumerate(chunks):
            embedding = await _embed_text(chunk)
            vector_value = _embedding_to_pgvector(embedding)
            await conn.execute(
                '''
                INSERT INTO agent_knowledge (
                    agent_id, source_url, chunk_text, embedding, chunk_index, is_active, created_at
                )
                VALUES ($1, $2, $3, $4::vector, $5, true, now())
                ''',
                agent_id,
                url,
                chunk,
                vector_value,
                chunk_index,
            )

        existing_sources_raw = await conn.fetchval(
            'SELECT knowledge_sources FROM hired_agents WHERE agent_id = $1',
            agent_id,
        )
        existing_sources = _to_json_compat(existing_sources_raw)
        if not isinstance(existing_sources, list):
            existing_sources = []
        existing_sources.append(
            {
                'url': url,
                'added_at': _iso_now(),
                'chunks': len(chunks),
            }
        )
        await conn.execute(
            '''
            UPDATE hired_agents
            SET knowledge_sources = $2::jsonb
            WHERE agent_id = $1
            ''',
            agent_id,
            json.dumps(existing_sources),
        )
    finally:
        await conn.close()


@router.get('')
async def list_agents():
    conn = await _connect()
    try:
        rows = await conn.fetch(
            '''
            SELECT agent_id, agent_name, role, goal, tool_whitelist, created_at
            FROM hired_agents
            WHERE is_active = true
            ORDER BY created_at DESC
            '''
        )
        result = []
        for row in rows:
            record = dict(row)
            record['tool_whitelist'] = _to_json_compat(record.get('tool_whitelist')) or []
            result.append(record)
        return result
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


@router.post('/{agent_id}/train')
async def train_agent(agent_id: str, req: TrainAgentRequest, background_tasks: BackgroundTasks):
    conn = await _connect()
    try:
        exists = await conn.fetchrow(
            'SELECT agent_id, is_active FROM hired_agents WHERE agent_id = $1',
            agent_id,
        )
        if not exists:
            raise HTTPException(status_code=404, detail='Agent not found')
        if not exists.get('is_active'):
            raise HTTPException(status_code=409, detail='Agent is inactive')
    finally:
        await conn.close()

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            check = await client.get(req.source_url)
            check.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f'Source URL not reachable: {exc}')

    background_tasks.add_task(_run_training, agent_id, req.source_url)
    return {
        'agent_id': agent_id,
        'status': 'training_started',
        'source_url': req.source_url,
        'started_at': _iso_now(),
    }
