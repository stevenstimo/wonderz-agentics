"""Platform Spec V3 — Lessons lifecycle API: decay check, propose, list."""
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.lessons_lifecycle import LessonsLifecycle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


class ProposeBody(BaseModel):
    task_id: str
    agent_id: str
    worker_output: dict = Field(default_factory=dict)


@router.post("/run-decay-check")
async def run_decay_check(pool=Depends(get_db)) -> dict[str, Any]:
    """Handmatige trigger voor lesson decay (platform spec V3)."""
    if not pool:
        return {"decayed": 0, "stale": 0, "duration_ms": 0}
    start = time.perf_counter()
    result = await LessonsLifecycle().decay_check(pool)
    duration_ms = int((time.perf_counter() - start) * 1000)
    return {"decayed": result["decayed"], "stale": result["stale"], "duration_ms": duration_ms}


@router.post("/propose", dependencies=[Depends(get_current_user)])
async def propose_lesson(body: ProposeBody, pool=Depends(get_db)):
    """Maak een nieuwe lesson (pending) en check contradictions."""
    if not pool:
        return {"lesson_id": "", "conflicts": []}
    lifecycle = LessonsLifecycle()
    lesson_id = await lifecycle.propose(
        pool, body.worker_output, body.task_id, body.agent_id
    )
    conflicts = await lifecycle.check_contradictions(pool, lesson_id)
    return {"lesson_id": lesson_id, "conflicts": conflicts}


@router.get("", dependencies=[Depends(get_current_user)])
async def list_lessons(
    pool=Depends(get_db),
    status: str = Query(default="active", description="active|pending|stale|rejected|all"),
    min_confidence: float = Query(default=0.0, ge=0, le=1),
):
    """Lijst lessons met optionele filter op status en min_confidence."""
    if not pool:
        return []
    async with pool.acquire() as conn:
        has_ls = await conn.fetchval(
            "SELECT 1 FROM information_schema.columns WHERE table_name = 'lessons' AND column_name = 'lesson_status'"
        )
        status_expr = "COALESCE(lesson_status, status)" if has_ls else "status"
        if status == "all":
            rows = await conn.fetch(
                f"""
                SELECT lesson_id, title, gevonden, oorzaak, fix, impact, agent_id, task_id,
                       confidence_score, {status_expr} AS lesson_status, usage_count, last_confirmed_at
                FROM lessons
                WHERE confidence_score >= $1
                ORDER BY last_confirmed_at DESC NULLS LAST, created_at DESC
                LIMIT 200
                """,
                min_confidence,
            )
        else:
            rows = await conn.fetch(
                f"""
                SELECT lesson_id, title, gevonden, oorzaak, fix, impact, agent_id, task_id,
                       confidence_score, {status_expr} AS lesson_status, usage_count, last_confirmed_at
                FROM lessons
                WHERE {status_expr} = $1 AND confidence_score >= $2
                ORDER BY last_confirmed_at DESC NULLS LAST, created_at DESC
                LIMIT 200
                """,
                status,
                min_confidence,
            )
    return [
        {
            "lesson_id": r["lesson_id"],
            "title": r["title"],
            "gevonden": r["gevonden"],
            "oorzaak": r["oorzaak"],
            "fix": r["fix"],
            "impact": r["impact"],
            "agent_id": r["agent_id"],
            "task_id": r["task_id"],
            "confidence_score": float(r["confidence_score"]) if r["confidence_score"] is not None else 0,
            "lesson_status": r["lesson_status"],
            "usage_count": r["usage_count"] or 0,
            "last_confirmed_at": r["last_confirmed_at"].isoformat() if r.get("last_confirmed_at") else None,
        }
        for r in rows
    ]
