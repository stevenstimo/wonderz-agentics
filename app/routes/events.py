"""Platform Spec V4 — Events API: GET /api/events voor traceability."""
import json
import logging
from typing import Any, Optional


def _coerce_payload(raw) -> dict:
    """Unwrap potentially double-encoded JSONB payload to a dict."""
    for _ in range(3):
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return {}
        else:
            break
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    return {"value": raw}

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

        where = (" AND ".join(conditions)) if conditions else "1=1"
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
            "payload": _coerce_payload(r.get("payload")),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]
    return {"events": events, "total": total}
