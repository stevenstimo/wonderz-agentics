"""
Agent Inbox — berichten tussen agents en CEO.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inbox", tags=["inbox"])


# --- Pydantic models ---

class InboxMessageCreate(BaseModel):
    from_agent_id: str = Field(..., min_length=1)
    to_agent_id: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    message_type: str = Field(default="info", pattern="^(info|gap_report|instruction|alert)$")
    urgency: str = Field(default="normal", pattern="^(low|normal|high|critical)$")
    job_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class InboxDispatchCreate(BaseModel):
    from_agent_id: str = Field(default="agent:ceo:mr-klein", min_length=1)
    to_agent_id: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    message_type: str = Field(default="instruction", pattern="^(info|gap_report|instruction|alert)$")
    urgency: str = Field(default="normal", pattern="^(low|normal|high|critical)$")
    job_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class InboxStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(read|actioned|dismissed)$")


def _row_to_message(row: Any) -> dict:
    if row is None:
        return {}
    d = dict(row)
    for k in ("created_at", "updated_at"):
        if k in d and d[k] is not None and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    if "job_id" in d and d["job_id"] is not None:
        d["job_id"] = str(d["job_id"])
    if "id" in d:
        d["id"] = str(d["id"])
    return d


@router.get("")
async def list_inbox(
    to_agent_id: Optional[str] = None,
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    limit: int = 100,
    db=Depends(get_db),
):
    """Alle berichten, optioneel gefilterd op to_agent_id, status, urgency."""
    conditions = []
    params = []
    i = 1
    if to_agent_id:
        conditions.append(f"to_agent_id = ${i}")
        params.append(to_agent_id)
        i += 1
    if status:
        conditions.append(f"status = ${i}")
        params.append(status)
        i += 1
    if urgency:
        conditions.append(f"urgency = ${i}")
        params.append(urgency)
        i += 1
    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)
    query = f"""
        SELECT id, from_agent_id, to_agent_id, subject, body, message_type,
               urgency, status, job_id, metadata, created_at
        FROM agent_inbox
        WHERE {where}
        ORDER BY
          CASE urgency
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'normal' THEN 3
            WHEN 'low' THEN 4
            ELSE 5
          END,
          created_at DESC
        LIMIT ${i}
    """
    async with db.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [_row_to_message(r) for r in rows]


@router.get("/summary")
async def inbox_summary(db=Depends(get_db)):
    """Badge counts: unread per agent."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT to_agent_id, COUNT(*) AS unread_count
            FROM agent_inbox
            WHERE status = 'unread'
            GROUP BY to_agent_id
            """
        )
    total = sum(r["unread_count"] for r in rows)
    by_agent = {str(r["to_agent_id"]): r["unread_count"] for r in rows}
    return {"total_unread": total, "by_agent": by_agent}


@router.post("")
async def create_message(req: InboxMessageCreate, db=Depends(get_db)):
    """Nieuw bericht sturen."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agent_inbox
            (from_agent_id, to_agent_id, subject, body, message_type, urgency, job_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            RETURNING id, from_agent_id, to_agent_id, subject, body, message_type,
                      urgency, status, job_id, metadata, created_at
            """,
            req.from_agent_id,
            req.to_agent_id,
            req.subject,
            req.body,
            req.message_type,
            req.urgency,
            req.job_id,
            __import__("json").dumps(req.metadata),
        )
    return _row_to_message(row)


@router.post("/dispatch")
async def dispatch_message(req: InboxDispatchCreate, db=Depends(get_db)):
    """CEO dispatch: bericht naar specifieke agent met job context."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agent_inbox
            (from_agent_id, to_agent_id, subject, body, message_type, urgency, job_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            RETURNING id, from_agent_id, to_agent_id, subject, body, message_type,
                      urgency, status, job_id, metadata, created_at
            """,
            req.from_agent_id or "agent:ceo:mr-klein",
            req.to_agent_id,
            req.subject,
            req.body,
            req.message_type,
            req.urgency,
            req.job_id,
            __import__("json").dumps(req.metadata),
        )
    return _row_to_message(row)


@router.get("/{message_id}")
async def get_message(message_id: str, db=Depends(get_db)):
    """Enkel bericht ophalen."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, from_agent_id, to_agent_id, subject, body, message_type,
                   urgency, status, job_id, metadata, created_at
            FROM agent_inbox
            WHERE id = $1
            """,
            message_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    return _row_to_message(row)


@router.patch("/{message_id}")
async def update_message_status(
    message_id: str,
    req: InboxStatusUpdate,
    db=Depends(get_db),
):
    """Status updaten (read/actioned/dismissed)."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE agent_inbox
            SET status = $1, updated_at = now()
            WHERE id = $2
            RETURNING id, from_agent_id, to_agent_id, subject, body, message_type,
                      urgency, status, job_id, metadata, created_at
            """,
            req.status,
            message_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    return _row_to_message(row)


@router.delete("/{message_id}")
async def delete_message(message_id: str, db=Depends(get_db)):
    """Bericht verwijderen."""
    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM agent_inbox WHERE id = $1",
            message_id,
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True}
