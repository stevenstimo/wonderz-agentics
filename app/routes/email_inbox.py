"""
Email Inbox API: inbound_emails for the current user, chat, convert to job, allowed senders.
All endpoints require authentication; list/detail filtered by user_id.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user
from app.services.inbox_job_convert import (
    convert_plan_ready_row_to_job,
    extract_latest_plan_from_chat,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


def _row_to_out(r: Any) -> dict:
    d = dict(r)
    for k in list(d.keys()):
        if hasattr(d.get(k), "isoformat"):
            d[k] = d[k].isoformat()
    if d.get("user_id") is not None:
        d["user_id"] = str(d["user_id"])
    if d.get("job_id") is not None:
        d["job_id"] = str(d["job_id"])
    return d


def _is_admin(user: TokenPayload) -> bool:
    return getattr(user, "role", "") == "super_admin"


@router.get("/summary")
async def inbox_summary(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> dict[str, Any]:
    """Return counts for sidebar badge and inbox overview."""
    pool = await get_db()
    user_id = str(current_user.user_id)
    admin = _is_admin(current_user)
    async with pool.acquire() as conn:
        if admin:
            total_row = await conn.fetchrow("SELECT count(*) AS cnt FROM inbound_emails")
            unread_row = await conn.fetchrow(
                "SELECT count(*) AS cnt FROM inbound_emails WHERE status IN ('new', 'in_chat')"
            )
            plan_ready_row = await conn.fetchrow(
                "SELECT count(*) AS cnt FROM inbound_emails WHERE status = 'plan_ready'"
            )
        else:
            total_row = await conn.fetchrow(
                "SELECT count(*) AS cnt FROM inbound_emails WHERE user_id = $1::uuid",
                user_id,
            )
            unread_row = await conn.fetchrow(
                """
                SELECT count(*) AS cnt FROM inbound_emails
                WHERE user_id = $1::uuid AND status IN ('new', 'in_chat')
                """,
                user_id,
            )
            plan_ready_row = await conn.fetchrow(
                """
                SELECT count(*) AS cnt FROM inbound_emails
                WHERE user_id = $1::uuid AND status = 'plan_ready'
                """,
                user_id,
            )
    return {
        "total": total_row["cnt"] if total_row else 0,
        "unread": unread_row["cnt"] if unread_row else 0,
        "plan_ready": plan_ready_row["cnt"] if plan_ready_row else 0,
        "total_unread": unread_row["cnt"] if unread_row else 0,
    }


@router.get("")
async def list_inbox(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """All inbound_emails for the current user (or all if super_admin), sorted by received_at DESC."""
    pool = await get_db()
    user_id = str(current_user.user_id)
    admin = _is_admin(current_user)
    async with pool.acquire() as conn:
        if admin:
            rows = await conn.fetch(
                """
                SELECT e.email_id, e.from_address, e.from_name, e.subject, e.status,
                       e.received_at, e.chat_id, e.job_id, e.completeness_score, e.user_id,
                       u.email AS owner_email
                FROM inbound_emails e
                LEFT JOIN users u ON u.id = e.user_id
                ORDER BY e.received_at DESC
                """,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT email_id, from_address, from_name, subject, status, received_at,
                       chat_id, job_id, completeness_score
                FROM inbound_emails
                WHERE user_id = $1::uuid
                ORDER BY received_at DESC
                """,
                user_id,
            )
    return [_row_to_out(r) for r in rows]


@router.get("/senders")
async def list_senders(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """List allowed senders (for current user or admin)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sender_id, email, user_id, display_name, is_active, added_at
            FROM inbox_allowed_senders
            WHERE is_active = true
            ORDER BY added_at ASC
            """
        )
    return [_row_to_out(r) for r in rows]


@router.post("/senders")
async def add_sender(
    body: dict[str, Any],
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> dict[str, Any]:
    """Add a new allowed sender. Body: { email, user_id, display_name }."""
    email = (body.get("email") or "").strip()
    user_id = (body.get("user_id") or "").strip()
    display_name = (body.get("display_name") or "").strip() or None
    if not email:
        raise HTTPException(status_code=400, detail="email required")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO inbox_allowed_senders (email, user_id, display_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name, user_id = EXCLUDED.user_id
            RETURNING sender_id, email, user_id, display_name, is_active, added_at
            """,
            email,
            user_id,
            display_name,
        )
    return _row_to_out(row)


@router.get("/{email_id}")
async def get_inbox_detail(
    email_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> dict[str, Any]:
    """Detail of one email plus full chat history."""
    pool = await get_db()
    user_id = str(current_user.user_id)
    admin = _is_admin(current_user)
    async with pool.acquire() as conn:
        if admin:
            row = await conn.fetchrow(
                """
                SELECT email_id, message_id, from_address, from_name, subject, body_clean,
                       received_at, status, chat_id, job_id, completeness_score, created_at
                FROM inbound_emails
                WHERE email_id = $1
                """,
                email_id,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT email_id, message_id, from_address, from_name, subject, body_clean,
                       received_at, status, chat_id, job_id, completeness_score, created_at
                FROM inbound_emails
                WHERE email_id = $1 AND user_id = $2::uuid
                """,
                email_id,
                user_id,
            )
        if not row:
            raise HTTPException(status_code=404, detail="Email not found")
        email_out = _row_to_out(row)
        chat_id = row.get("chat_id")
        if chat_id:
            chat_row = await conn.fetchrow(
                "SELECT agent_id FROM direct_chats WHERE chat_id = $1",
                chat_id,
            )
            if chat_row:
                email_out["agent_id"] = chat_row["agent_id"]
            msg_rows = await conn.fetch(
                """
                SELECT message_id, chat_id, role, content, created_at
                FROM direct_chat_messages
                WHERE chat_id = $1
                ORDER BY message_id ASC
                """,
                chat_id,
            )
            messages_out = [_row_to_out(m) for m in msg_rows]
        else:
            messages_out = []
    return {"email": email_out, "messages": messages_out}


@router.post("/{email_id}/convert")
async def convert_to_job(
    email_id: str,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> dict[str, Any]:
    """Convert inbox email to Job. Requires status plan_ready; uses last %%PLAN%% in chat."""
    pool = await get_db()
    user_id = str(current_user.user_id)
    admin = _is_admin(current_user)
    async with pool.acquire() as conn:
        if admin:
            row = await conn.fetchrow(
                """
                SELECT email_id, status, chat_id, subject, user_id
                FROM inbound_emails
                WHERE email_id = $1
                """,
                email_id,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT email_id, status, chat_id, subject, user_id
                FROM inbound_emails
                WHERE email_id = $1 AND user_id = $2::uuid
                """,
                email_id,
                user_id,
            )
        if not row:
            raise HTTPException(status_code=404, detail="Email not found")
        if row["status"] != "plan_ready":
            raise HTTPException(
                status_code=400,
                detail=f"Email must have status plan_ready (current: {row['status']})",
            )
        chat_id = row.get("chat_id")
        if not chat_id:
            raise HTTPException(status_code=400, detail="No chat linked to this email")
        plan_data = await extract_latest_plan_from_chat(conn, chat_id)
        if not plan_data:
            raise HTTPException(status_code=400, detail="No %%PLAN%% block found in chat")
        # Use the email owner's user_id for the job, not the admin's
        job_owner_id = str(row["user_id"]) if row.get("user_id") else user_id
        job_id = await convert_plan_ready_row_to_job(
            conn,
            email_id=email_id,
            subject=row.get("subject"),
            job_owner_id=job_owner_id,
            plan_data=plan_data,
        )
    return {"job_id": job_id}