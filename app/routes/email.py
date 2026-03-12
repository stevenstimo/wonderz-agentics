"""
Email Intake Channel §7: Audit and dev endpoints for inbound emails.
- GET /api/email/inbox: list inbound_emails (admin/super_admin only), optional status filter, no body_raw.
- GET /api/email/{email_id}: detail one record; score_breakdown from job.context if linked.
- POST /api/email/poll: trigger one poll (development only).
"""
import os
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user, require_admin_or_super_admin

router = APIRouter(prefix="/api/email", tags=["email"])


@router.get("/inbox")
async def get_inbox(
    current_user: Annotated[TokenPayload, Depends(require_admin_or_super_admin)],
    status: Optional[str] = Query(None, description="Filter by status"),
) -> list[dict[str, Any]]:
    """List inbound_emails for audit. Never returns body_raw; includes body_clean. Filter by status if given."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT email_id, message_id, from_address, from_name, subject,
                       body_clean, received_at, processed_at, status,
                       user_id, job_id, completeness_score, error_detail, created_at
                FROM inbound_emails
                WHERE status = $1
                ORDER BY received_at DESC
                """,
                status,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT email_id, message_id, from_address, from_name, subject,
                       body_clean, received_at, processed_at, status,
                       user_id, job_id, completeness_score, error_detail, created_at
                FROM inbound_emails
                ORDER BY received_at DESC
                """
            )
    return [dict(r) for r in rows]


@router.get("/{email_id}")
async def get_email_detail(
    email_id: str,
    current_user: Annotated[TokenPayload, Depends(require_admin_or_super_admin)],
) -> dict[str, Any]:
    """Detail of one inbound email. score_breakdown from job.context when job_id is set."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT email_id, message_id, from_address, from_name, subject,
                   body_raw, body_clean, received_at, processed_at, status,
                   user_id, job_id, completeness_score, error_detail, created_at
            FROM inbound_emails
            WHERE email_id = $1
            """,
            email_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Email not found")
        out = dict(row)
        if row.get("job_id"):
            job_row = await conn.fetchrow(
                "SELECT context FROM jobs WHERE id = $1",
                str(row["job_id"]),
            )
            if job_row and job_row.get("context"):
                ctx = job_row["context"]
                if isinstance(ctx, dict):
                    out["score_breakdown"] = ctx.get("score_breakdown")
                else:
                    out["score_breakdown"] = None
            else:
                out["score_breakdown"] = None
        else:
            out["score_breakdown"] = None
    return out


@router.post("/poll")
async def post_poll(
    current_user: Annotated[TokenPayload, Depends(require_admin_or_super_admin)],
) -> dict[str, Any]:
    """Trigger one EmailPoller cycle. Only when ENV=development; otherwise 403."""
    if os.getenv("ENV") != "development":
        raise HTTPException(
            status_code=403,
            detail="Poll endpoint only available when ENV=development",
        )
    gmail_address = (os.getenv("GMAIL_ADDRESS") or "").strip()
    app_password = (os.getenv("GMAIL_APP_PASSWORD") or "").strip()
    if not gmail_address or not app_password:
        raise HTTPException(
            status_code=503,
            detail="GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set to poll",
        )
    from app.services.email_poller import EmailPoller
    poller = EmailPoller(gmail_address=gmail_address, app_password=app_password)
    await poller.poll_once()
    return {"status": "ok", "message": "Poll completed"}
