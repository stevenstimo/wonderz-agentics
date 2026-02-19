"""Talent pool API routes.

CRUD for the talents table + promote-to-crew.
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
router = APIRouter(prefix="/api/talents", tags=["talents"])


class CreateTalentRequest(BaseModel):
    name: str
    persona: Optional[str] = ""
    quality: Optional[str] = ""
    growth: Optional[str] = ""
    skills: Optional[list] = []
    avatar_url: Optional[str] = None


class UpdateTalentRequest(BaseModel):
    name: Optional[str] = None
    persona: Optional[str] = None
    quality: Optional[str] = None
    growth: Optional[str] = None
    skills: Optional[list] = None
    avatar_url: Optional[str] = None


class PromoteTalentRequest(BaseModel):
    role: str
    specialization: Optional[str] = None
    system_instructions: Optional[str] = ""
    hiring_logic: Optional[str] = ""


def _row_to_dict(row):
    """Convert a talent DB row to a JSON-safe dict."""
    d = dict(row)
    d["skills"] = json.loads(d["skills"]) if d.get("skills") else []
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    return d


@router.get("")
async def list_talents():
    """List all talents."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM talents ORDER BY created_at DESC")

    return [_row_to_dict(r) for r in rows]


@router.get("/{talent_id}")
async def get_talent(talent_id: str):
    """Get a single talent."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM talents WHERE id = $1", talent_id)

    if not row:
        raise HTTPException(status_code=404, detail="Talent not found")
    return _row_to_dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_talent(req: CreateTalentRequest):
    """Create a new talent."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    talent_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO talents (id, name, persona, quality, growth, skills, avatar_url, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """,
            talent_id,
            req.name,
            req.persona or "",
            req.quality or "",
            req.growth or "",
            json.dumps(req.skills or []),
            req.avatar_url,
        )

    logger.info(f"Created talent {talent_id}: {req.name}")
    return {
        "id": talent_id,
        "name": req.name,
        "persona": req.persona or "",
        "quality": req.quality or "",
        "growth": req.growth or "",
        "skills": req.skills or [],
        "avatar_url": req.avatar_url,
    }


@router.put("/{talent_id}")
async def update_talent(talent_id: str, req: UpdateTalentRequest):
    """Update a talent's fields."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    updates = []
    params = []
    idx = 1

    if req.name is not None:
        updates.append(f"name = ${idx}")
        params.append(req.name)
        idx += 1
    if req.persona is not None:
        updates.append(f"persona = ${idx}")
        params.append(req.persona)
        idx += 1
    if req.quality is not None:
        updates.append(f"quality = ${idx}")
        params.append(req.quality)
        idx += 1
    if req.growth is not None:
        updates.append(f"growth = ${idx}")
        params.append(req.growth)
        idx += 1
    if req.skills is not None:
        updates.append(f"skills = ${idx}")
        params.append(json.dumps(req.skills))
        idx += 1
    if req.avatar_url is not None:
        updates.append(f"avatar_url = ${idx}")
        params.append(req.avatar_url)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(talent_id)
    query = f"UPDATE talents SET {', '.join(updates)} WHERE id = ${idx}"

    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Talent not found")

    return {"id": talent_id, "updated": True}


@router.post("/{talent_id}/promote")
async def promote_talent(talent_id: str, req: PromoteTalentRequest):
    """Promote a talent to a hired agent (crew member)."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        talent = await conn.fetchrow("SELECT * FROM talents WHERE id = $1", talent_id)
        if not talent:
            raise HTTPException(status_code=404, detail="Talent not found")

        agent_id = f"agent:{req.role}:{uuid.uuid4().hex[:8]}"

        await conn.execute(
            """
            INSERT INTO hired_agents (
                agent_id, name, role, specialization, status,
                system_instructions, tool_access_whitelist,
                hiring_logic, hired_at, updated_at
            )
            VALUES ($1, $2, $3, $4, 'active', $5, '[]', $6, NOW(), NOW())
            """,
            agent_id,
            talent["name"],
            req.role,
            req.specialization or talent["persona"] or "",
            req.system_instructions or "",
            req.hiring_logic or "",
        )

        # Remove from talent pool after promotion
        await conn.execute("DELETE FROM talents WHERE id = $1", talent_id)

    logger.info(f"Promoted talent {talent_id} ({talent['name']}) to agent {agent_id}")
    return {
        "agent_id": agent_id,
        "name": talent["name"],
        "role": req.role,
        "status": "active",
        "promoted_from_talent": talent_id,
    }
