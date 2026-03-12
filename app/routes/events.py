"""Platform Spec V4 — Events API: GET /api/events voor traceability."""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", dependencies=[Depends(get_current_user)])
async def list_events(
    pool=Depends(get_db),
    job_id: Optional[str] = Query(None, description="Filter by job_id"),
    task_id: Optional[str] = Query(None, description="Filter by task_id"),
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """
    Haalt events op. Minimaal één van job_id of task_id aanbevolen voor gerichte resultaten.
    Response: { events: [...], total: int }.
    """
    if not pool:
        return {"events": [], "total": 0}

    async with pool.acquire() as conn:
        conditions = []
        params: list[Any] = []
        idx = 1

        if job_id:
            conditions.append(f"job_id = ${idx}")
            params.append(job_id)
            idx += 1
        if task_id:
            conditions.append(f"task_id = ${idx}")
            params.append(task_id)
            idx += 1
        if event_type:
            conditions.append(f"event_type = ${idx}")
            params.append(event_type)
            idx += 1

        where = (" AND " + " AND ".join(conditions)) if conditions else "1=1"
        params.append(limit)

        rows = await conn.fetch(
            f"""
            SELECT event_id, event_type, agent_id, task_id, job_id, lesson_id,
                   confidence_score, payload, created_at
            FROM events
            WHERE {where}
            ORDER BY created_at ASC
            LIMIT ${idx}
            """,
            *params,
        )
        total = len(rows)

    events = [
        {
            "event_id": str(r["event_id"]) if r.get("event_id") else None,
            "event_type": r.get("event_type"),
            "agent_id": r.get("agent_id"),
            "task_id": r.get("task_id"),
            "job_id": r.get("job_id"),
            "lesson_id": r.get("lesson_id"),
            "confidence_score": float(r["confidence_score"]) if r.get("confidence_score") is not None else None,
            "payload": dict(r["payload"]) if r.get("payload") is not None else {},
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]
    return {"events": events, "total": total}
