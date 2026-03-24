"""CEO skill_registry — deterministische skills (los van agent_skills library)."""

from __future__ import annotations

import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.services.skill_matcher import get_all_skills

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skill-registry", tags=["skill-registry"])


def _row_json(row: asyncpg.Record) -> dict[str, Any]:
    d = dict(row)
    if d.get("trigger_keywords") is not None:
        d["trigger_keywords"] = list(d["trigger_keywords"])
    for k in ("created_at",):
        if d.get(k) is not None and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    return d


@router.get("")
async def list_skill_registry(
    active_only: bool = True,
    pool: asyncpg.Pool = Depends(get_db),
):
    """Alle skills uit skill_registry (standaard alleen actief)."""
    async with pool.acquire() as conn:
        skills = await get_all_skills(conn)
    if active_only:
        skills = [s for s in skills if s.get("is_active", True)]
    return {"skills": skills, "total": len(skills)}


@router.get("/{skill_id}")
async def get_skill_registry_item(skill_id: str, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM skill_registry WHERE skill_id = $1",
            skill_id,
        )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill niet gevonden")
    return _row_json(row)


@router.post("/{skill_id}/activate", status_code=status.HTTP_200_OK)
async def activate_skill_registry_item(skill_id: str, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE skill_registry SET is_active = true WHERE skill_id = $1
            """,
            skill_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill niet gevonden")
    return {"skill_id": skill_id, "is_active": True}


@router.post("/{skill_id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_skill_registry_item(skill_id: str, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE skill_registry SET is_active = false WHERE skill_id = $1
            """,
            skill_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill niet gevonden")
    return {"skill_id": skill_id, "is_active": False}
