"""
Shared inbox → job conversion (plan_ready) and optional chat approval shortcut.

Used by /api/inbox/.../convert and by direct chat when the user sends an approval message.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional

from app.services.inbox_engine import _extract_plan_block
from app.services.job_pipeline import _insert_plan_steps, _json_default
from models.unified import ExecutionPlan, JobStep, StrategicBrief

logger = logging.getLogger(__name__)

# Minimum plan score required before auto-convert on chat approval (matches inbox CEO prompt).
MIN_PLAN_SCORE_FOR_JOB = 0.7

_APPROVAL_NEGATION = re.compile(
    r"\b(niet|geen|no|not|reject|afkeur|afwijs|don't|dont)\b",
    re.IGNORECASE,
)
_APPROVAL_HINT = re.compile(
    r"\b(akkoord|goedgekeurd|keur\s+goed|goedkeuring|approved|approve|"
    r"prima|akkoord\s+met|het\s+plan\s+klopt|plan\s+is\s+goed|"
    r"start\s+(de\s+)?job|looks\s+good|lgtm)\b",
    re.IGNORECASE,
)


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


def message_indicates_plan_approval(text: str) -> bool:
    """True if a short user message clearly approves the proposed plan (NL/EN)."""
    raw = (text or "").strip()
    if not raw or len(raw) > 400:
        return False
    if _APPROVAL_NEGATION.search(raw):
        return False
    return bool(_APPROVAL_HINT.search(raw))


def _plan_score_ok(plan_data: dict) -> bool:
    s = plan_data.get("completeness_score")
    if not isinstance(s, (int, float)):
        return False
    return float(s) >= MIN_PLAN_SCORE_FOR_JOB


async def extract_latest_plan_from_chat(conn, chat_id: str) -> Optional[dict]:
    """Return parsed %%PLAN%% JSON from the latest agent/assistant message, if any."""
    msg_rows = await conn.fetch(
        """
        SELECT content FROM direct_chat_messages
        WHERE chat_id = $1 AND role IN ('agent', 'assistant')
        ORDER BY message_id DESC
        """,
        chat_id,
    )
    for m in msg_rows:
        plan_data = _extract_plan_block(m.get("content") or "")
        if plan_data:
            return plan_data
    return None


async def convert_plan_ready_row_to_job(
    conn,
    *,
    email_id: str,
    subject: str | None,
    job_owner_id: str,
    plan_data: dict,
) -> str:
    """
    Insert job + job steps and mark inbound email converted_to_job.
    Caller must ensure inbound row is still plan_ready (transaction).
    """
    job_id = str(uuid.uuid4())
    context: dict[str, Any] = {
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
        subject or "Email job",
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
    return job_id


async def try_convert_inbox_chat_on_approval(
    pool,
    chat_id: str,
    user_id: str,
    user_message: str,
) -> Optional[dict[str, Any]]:
    """
    If this chat is linked to a plan_ready inbound email, the user message is a clear approval,
    and the latest plan has completeness_score >= MIN_PLAN_SCORE_FOR_JOB: create job, persist
    user + assistant confirmation messages, return API-shaped dict (else None).

    user_message should be the raw UI text (not client-context enriched).
    """
    if not message_indicates_plan_approval(user_message):
        return None

    from app.orchestration.direct_chat_engine import (  # noqa: PLC0415 — avoid import cycle
        DirectChatEngine,
        SOFT_TOKEN_LIMIT,
    )

    job_id: str | None = None
    assistant_message_id: int | None = None
    confirm_text = ""
    session_tokens = 0
    email_id_logged: str | None = None

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT email_id, status, chat_id, subject, user_id
                FROM inbound_emails
                WHERE chat_id = $1 AND user_id = $2::uuid AND status = 'plan_ready'
                """,
                chat_id,
                user_id,
            )
            if not row:
                return None

            plan_data = await extract_latest_plan_from_chat(conn, chat_id)
            if not plan_data or not _plan_score_ok(plan_data):
                logger.info(
                    "inbox approval skipped: no valid plan or score < %s chat_id=%s",
                    MIN_PLAN_SCORE_FOR_JOB,
                    chat_id,
                )
                return None

            job_owner_id = str(row["user_id"]) if row.get("user_id") else user_id
            job_id = await convert_plan_ready_row_to_job(
                conn,
                email_id=row["email_id"],
                subject=row.get("subject"),
                job_owner_id=job_owner_id,
                plan_data=plan_data,
            )
            email_id_logged = str(row["email_id"])

            engine = DirectChatEngine()
            await engine._save_message(conn, chat_id, "user", user_message, 0)
            confirm_text = (
                f"✅ Job aangemaakt: [{job_id}] — [klik om te openen](/jobs/{job_id})"
            )
            msg_row = await engine._save_message(conn, chat_id, "assistant", confirm_text, 0)
            assistant_message_id = int(msg_row["message_id"])

            chat_row = await conn.fetchrow(
                "SELECT token_used FROM direct_chats WHERE chat_id = $1",
                chat_id,
            )
            session_tokens = int(chat_row["token_used"] or 0) if chat_row else 0

    if job_id and email_id_logged:
        logger.info(
            "inbox chat approval: converted email_id=%s to job_id=%s chat_id=%s",
            email_id_logged,
            job_id,
            chat_id,
        )
    return {
        "chat_id": chat_id,
        "message_id": assistant_message_id,
        "agent_response": confirm_text,
        "token_usage": 0,
        "session_tokens_used": session_tokens,
        "soft_limit": SOFT_TOKEN_LIMIT,
        "job_id": job_id,
    }
