"""Skill Factory API — manage standalone skill objects.

Important: this module intentionally exposes its own prefix (`/api/skill-factory`)
so the existing `/api/skills` endpoint (agent_skills model) and CrewDetail.jsx
remain unchanged.
"""

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import get_db
from app.middleware.auth import get_current_user, TokenPayload


router = APIRouter(
    prefix="/api/skill-factory",
    tags=["skill-factory"],
    dependencies=[Depends(get_current_user)],
)


class CreateSkillFactoryRequest(BaseModel):
    # Required: snake_case identifier (e.g. "write_landing_page")
    name: str = Field(..., min_length=1)
    display_name: Optional[str] = None
    description: Optional[str] = None
    trigger_condition: Optional[str] = None
    requires_tools: List[str] = Field(default_factory=list)
    requires_skills: List[str] = Field(default_factory=list)
    # Optional: link to one or more agents by agent_id
    agent_ids: List[str] = Field(default_factory=list)
    status: str = "active"


class UpdateSkillFactoryRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    trigger_condition: Optional[str] = None
    requires_tools: Optional[List[str]] = None
    requires_skills: Optional[List[str]] = None
    status: Optional[str] = None


def _slugify_skill_name(name: str) -> str:
    # The frontend validates snake_case; backend enforces a compatible subset.
    slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    return slug


def _skill_id_from_name(name: str) -> str:
    slug = _slugify_skill_name(name)
    if not slug:
        raise HTTPException(status_code=422, detail="Invalid skill name")
    return f"skill:{slug}"


def _serialize_skill_row(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k in ("created_at", "updated_at"):
        v = d.get(k)
        if v is not None and hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _validate_status(status: str) -> str:
    allowed = ("active", "inactive", "draft")
    status_norm = (status or "").lower().strip()
    if status_norm not in allowed:
        raise HTTPException(status_code=422, detail=f"status must be one of {allowed}")
    return status_norm


@router.get("")
async def list_skill_factory_skills(
    # NOTE: no filters in v1; keep contract stable for the SkillFactory page.
) -> Dict[str, Any]:
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              s.*,
              (
                SELECT COUNT(*)
                FROM hired_agents ha
                WHERE ha.skills @> to_jsonb(ARRAY[s.name]::text[])
              ) AS linked_agents_count
            FROM skills s
            ORDER BY s.created_at DESC
            """
        )
    skills = [_serialize_skill_row(r) for r in rows]
    return {"skills": skills, "total": len(skills)}


@router.get("/{skill_id}")
async def get_skill_factory_skill(skill_id: str) -> Dict[str, Any]:
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
              s.*,
              (
                SELECT COUNT(*)
                FROM hired_agents ha
                WHERE ha.skills @> to_jsonb(ARRAY[s.name]::text[])
              ) AS linked_agents_count
            FROM skills s
            WHERE s.skill_id = $1
            """,
            skill_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _serialize_skill_row(row)


@router.post("")
async def create_skill_factory_skill(
    req: CreateSkillFactoryRequest,
    current_user: TokenPayload = Depends(get_current_user),
) -> Dict[str, Any]:
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    # Client expects snake_case and validates, but enforce again for safety.
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise HTTPException(
            status_code=422,
            detail="name must contain only lowercase letters, digits and underscores",
        )

    status = _validate_status(req.status)
    display_name = (req.display_name or "").strip() or name
    trigger_condition = (req.trigger_condition or "").strip() or None
    description = (req.description or "").strip() or None

    skill_id = _skill_id_from_name(name)

    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT skill_id FROM skills WHERE name = $1", name)
        if existing:
            raise HTTPException(status_code=409, detail=f"Skill '{name}' already exists")

        await conn.execute(
            """
            INSERT INTO skills (
              skill_id, name, display_name, description,
              trigger_condition, requires_tools, requires_skills, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            skill_id,
            name,
            display_name,
            description,
            trigger_condition,
            req.requires_tools or [],
            req.requires_skills or [],
            status,
        )

        # Optional: link to agents by agent_id
        if req.agent_ids:
            for agent_id in req.agent_ids:
                agent_id_norm = (agent_id or "").strip()
                if not agent_id_norm:
                    continue
                await conn.execute(
                    """
                    UPDATE hired_agents
                    SET skills = skills || to_jsonb(ARRAY[$1]::text[]),
                        updated_at = now()
                    WHERE agent_id = $2
                      AND NOT (skills @> to_jsonb(ARRAY[$1]::text[]))
                    """,
                    name,
                    agent_id_norm,
                )

    return {"skill_id": skill_id, "name": name, "status": "created", "created_by": current_user.user_id}


@router.patch("/{skill_id}")
async def patch_skill_factory_skill(
    skill_id: str,
    req: UpdateSkillFactoryRequest,
) -> Dict[str, Any]:
    pool = await get_db()

    fields: Dict[str, Any] = req.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided")

    set_clauses: List[str] = []
    values: List[Any] = []
    idx = 1

    def add_clause(col: str, val: Any) -> None:
        nonlocal idx
        set_clauses.append(f"{col} = ${idx}")
        values.append(val)
        idx += 1

    if "display_name" in fields:
        v = (fields["display_name"] or "").strip()
        if not v:
            raise HTTPException(status_code=422, detail="display_name cannot be empty")
        add_clause("display_name", v)

    if "description" in fields:
        v = (fields["description"] or "").strip()
        add_clause("description", v or None)

    if "trigger_condition" in fields:
        v = (fields["trigger_condition"] or "").strip()
        add_clause("trigger_condition", v or None)

    if "requires_tools" in fields:
        add_clause("requires_tools", fields["requires_tools"] or [])

    if "requires_skills" in fields:
        add_clause("requires_skills", fields["requires_skills"] or [])

    if "status" in fields:
        status_val = fields["status"]
        if status_val is None:
            raise HTTPException(status_code=422, detail="status cannot be null")
        add_clause("status", _validate_status(status_val))

    if not set_clauses:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    values.append(skill_id)
    where_placeholder = f"${len(values)}"

    sql = f"""
      UPDATE skills
      SET {', '.join(set_clauses)}, updated_at = now()
      WHERE skill_id = {where_placeholder}
      RETURNING
        skill_id, name, display_name, description, trigger_condition,
        requires_tools, requires_skills, status, created_at, updated_at
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *values)

    if not row:
        raise HTTPException(status_code=404, detail="Skill not found")

    return _serialize_skill_row(row)

