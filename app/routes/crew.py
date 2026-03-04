"""Crew management API routes.

CRUD for the crew_members table.
"""

import uuid
import json
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

import app.db as _db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crew", tags=["crew"])


def _row_to_dict(row):
    """Convert a crew_members DB row to a JSON-safe dict."""
    d = dict(row)
    d["id"] = str(d["id"])
    for field in ("permissions", "knowledge_base_sources", "tool_access_whitelist"):
        val = d.get(field)
        if val is None:
            d[field] = []
        elif isinstance(val, str):
            try:
                d[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    for ts_field in ("created_at", "updated_at"):
        if d.get(ts_field):
            d[ts_field] = d[ts_field].isoformat()
    return d


class CreateCrewMemberRequest(BaseModel):
    name: str
    role: str
    specialization: Optional[str] = ""
    avatar_url: Optional[str] = None
    system_instructions: Optional[str] = ""
    knowledge_base_sources: Optional[str] = ""
    tool_access_whitelist: Optional[str] = ""
    hiring_logic: Optional[str] = ""
    persona: Optional[str] = ""
    quality_notes: Optional[str] = ""
    development_notes: Optional[str] = ""


class UpdateCrewMemberRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    specialization: Optional[str] = None
    status: Optional[str] = None
    avatar_url: Optional[str] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[str] = None
    tool_access_whitelist: Optional[str] = None
    hiring_logic: Optional[str] = None
    persona: Optional[str] = None
    quality_notes: Optional[str] = None
    development_notes: Optional[str] = None


@router.get("")
async def list_crew():
    """List all crew members from the database."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM crew_members ORDER BY name ASC"
        )

    return [_row_to_dict(r) for r in rows]


@router.get("/{member_id}")
async def get_crew_member(member_id: str):
    """Get a single crew member."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM crew_members WHERE id::text = $1", member_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Crew member not found")
    return _row_to_dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_crew_member(req: CreateCrewMemberRequest):
    """Create a new crew member."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    member_id = str(uuid.uuid4())
    crew_id = str(uuid.uuid4())

    # Parse comma-separated lists into JSON arrays
    def _parse_list(val):
        if not val:
            return json.dumps([])
        items = [s.strip() for s in val.split(",") if s.strip()] if isinstance(val, str) else val
        return json.dumps(items)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO crew_members (
                id, crew_id, name, role, specialization, status,
                avatar_url, system_instructions, knowledge_base_sources,
                tool_access_whitelist, hiring_logic,
                persona, quality_notes, development_notes,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, 'active',
                $6, $7, $8::jsonb,
                $9::jsonb, $10,
                $11, $12, $13,
                NOW(), NOW()
            )
            """,
            member_id, crew_id, req.name, req.role, req.specialization or "",
            req.avatar_url, req.system_instructions or "",
            _parse_list(req.knowledge_base_sources),
            _parse_list(req.tool_access_whitelist),
            req.hiring_logic or "",
            req.persona or "", req.quality_notes or "", req.development_notes or "",
        )

    logger.info(f"Created crew member {member_id}: {req.name} ({req.role})")
    return {
        "id": member_id,
        "name": req.name,
        "role": req.role,
        "status": "active",
    }


@router.put("/{member_id}")
async def update_crew_member(member_id: str, req: UpdateCrewMemberRequest):
    """Update a crew member."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    updates = []
    params = []
    idx = 1

    field_map = {
        "name": "name", "role": "role", "specialization": "specialization",
        "status": "status", "avatar_url": "avatar_url",
        "system_instructions": "system_instructions",
        "hiring_logic": "hiring_logic", "persona": "persona",
        "quality_notes": "quality_notes", "development_notes": "development_notes",
    }

    for attr, col in field_map.items():
        val = getattr(req, attr, None)
        if val is not None:
            updates.append(f"{col} = ${idx}")
            params.append(val)
            idx += 1

    # List fields stored as jsonb
    for attr in ("knowledge_base_sources", "tool_access_whitelist"):
        val = getattr(req, attr, None)
        if val is not None:
            items = [s.strip() for s in val.split(",") if s.strip()] if isinstance(val, str) else val
            updates.append(f"{attr} = ${idx}::jsonb")
            params.append(json.dumps(items))
            idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")
    params.append(member_id)

    query = f"UPDATE crew_members SET {', '.join(updates)} WHERE id::text = ${idx}"

    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Crew member not found")

    return {"id": member_id, "updated": True}


@router.delete("/{member_id}")
async def delete_crew_member(member_id: str):
    """Delete a crew member."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM crew_members WHERE id::text = $1", member_id
        )

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Crew member not found")

    return {"id": member_id, "deleted": True}
