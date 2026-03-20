"""
Email Inbox API: inbound_emails for the current user, chat, convert to job, allowed senders.
All endpoints require authentication; list/detail filtered by user_id.
"""

import json
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user
from app.services.inbox_engine import _extract_plan_block
from app.services.job_pipeline import _insert_plan_steps, _json_default
from models.unified import ExecutionPlan, JobStep, StrategicBrief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


def _ceo_plan_to_execution_plan(ceo_plan: dict) -> ExecutionPlan:
    """Build ExecutionPlan from CEO %%PLAN%% JSON for _insert_plan_steps."""
    steps_raw = ceo_plan.get("steps") or []
    steps: list[JobStep] = []
    for i, s in enumerate(steps_raw, 1):
        if not isinstance(s, dict):
            continue
        steps.append(
            JobStep(
                step_index=i,
                agent_role=str(s.get("agent_role") or "copywriter"),
                unified_tool=str(s.get("unified_tool") or "write_content"),
                requires_approval=bool(s.get("requires_approval", False)),
                description=str(s.get("description") or ""),
            )
        )
    brief = StrategicBrief(
        job_post="",
        is_complete=True,
        clarifications=[],
        context={},
        message=None,
    )
    return ExecutionPlan(brief=brief, steps=steps, hired_agents=[], estimated_duration_seconds=0)


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
        msg_rows = await conn.fetch(
            """
            SELECT content FROM direct_chat_messages
            WHERE chat_id = $1 AND role = 'agent'
            ORDER BY message_id DESC
            """,
            chat_id,
        )
        plan_data = None
        for m in msg_rows:
            plan_data = _extract_plan_block(m.get("content") or "")
            if plan_data:
                break
        if not plan_data:
            raise HTTPException(status_code=400, detail="No %%PLAN%% block found in chat")
        job_id = str(uuid.uuid4())
        # Use the email owner's user_id for the job, not the admin's
        job_owner_id = str(row["user_id"]) if row.get("user_id") else user_id
        context = {
            "plan": plan_data,
            "completeness_score": plan_data.get("completeness_score"),
            "assumptions": plan_data.get("assumptions") or [],
        }
        await conn.execute(
            """
            INSERT INTO jobs (
                id, user_id, job_post, status, source_platform, context,
                token_budget, job_type, intake_source, inbound_email_id
            )
            VALUES ($1, $2::uuid, $3, $4, $5, $6::jsonb, $7, $8, $9, $10)
            """,
            job_id,
            job_owner_id,
            row["subject"] or "Email job",
            "PLAN_PROPOSED",
            "web",
            json.dumps(context, default=_json_default),
            50000,
            "email",
            "email",
            email_id,
        )
        plan = _ceo_plan_to_execution_plan(plan_data)
        await _insert_plan_steps(conn, job_id, plan)
        await conn.execute(
            """
            UPDATE inbound_emails SET status = $1, job_id = $2::uuid WHERE email_id = $3
            """,
            "converted_to_job",
            job_id,
            email_id,
        )
    return {"job_id": job_id}