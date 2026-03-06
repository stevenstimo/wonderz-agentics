"""
Debug Chat: AI assistant for diagnosing jobs and platform issues.
Uses Claude Haiku with database context derived from the user message.
"""

import json
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db
from anthropic import Anthropic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debug", tags=["debug"])


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "hex"):  # UUID
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class DebugChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []  # [{role: str, content: str}]


def _row_to_dict(row: Any) -> dict:
    if row is None:
        return {}
    if hasattr(row, "__iter__") and not isinstance(row, (str, bytes, dict)):
        return dict(row)
    return dict(row)


async def _gather_context(conn, message: str) -> tuple[dict, dict]:
    """
    Parse user message and run relevant DB queries.
    Returns (context_dict for prompt, query_results summary).
    """
    msg_lower = message.strip().lower()
    context_parts = []
    query_results = {}

    # UUID: single job by id
    uuid_match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        message,
    )
    if uuid_match:
        job_id = uuid_match.group(0)
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
        if job:
            job_d = _row_to_dict(job)
            steps = await conn.fetch(
                "SELECT * FROM job_steps WHERE job_id=$1 ORDER BY step_index", job_id
            )
            clarifications = await conn.fetch(
                "SELECT * FROM clarifications WHERE job_id=$1 ORDER BY asked_at DESC NULLS LAST",
                job_id,
            )
            context_parts.append(
                "=== Job (by UUID) ===\n"
                + json.dumps(job_d, default=_json_default, indent=2)
            )
            context_parts.append(
                "=== Job steps ===\n"
                + json.dumps([_row_to_dict(s) for s in steps], default=_json_default, indent=2)
            )
            context_parts.append(
                "=== Clarifications ===\n"
                + json.dumps(
                    [_row_to_dict(c) for c in clarifications],
                    default=_json_default,
                    indent=2,
                )
            )
            query_results["job_id"] = job_id
            query_results["steps_count"] = len(steps)
            query_results["clarifications_count"] = len(clarifications)
            return "\n\n".join(context_parts), query_results

    # #NNNN: job by job_number in context
    hash_num = re.search(r"#(\d{4})", message)
    if hash_num:
        num = hash_num.group(1)
        job = await conn.fetchrow(
            "SELECT * FROM jobs WHERE context->>'job_number'=$1 ORDER BY created_at DESC LIMIT 1",
            num,
        )
        if job:
            job_id = str(job["id"])
            job_d = _row_to_dict(job)
            steps = await conn.fetch(
                "SELECT * FROM job_steps WHERE job_id=$1 ORDER BY step_index", job_id
            )
            clarifications = await conn.fetch(
                "SELECT * FROM clarifications WHERE job_id=$1 ORDER BY asked_at DESC NULLS LAST",
                job_id,
            )
            context_parts.append(
                "=== Job (by #"
                + num
                + ") ===\n"
                + json.dumps(job_d, default=_json_default, indent=2)
            )
            context_parts.append(
                "=== Job steps ===\n"
                + json.dumps([_row_to_dict(s) for s in steps], default=_json_default, indent=2)
            )
            context_parts.append(
                "=== Clarifications ===\n"
                + json.dumps(
                    [_row_to_dict(c) for c in clarifications],
                    default=_json_default,
                    indent=2,
                )
            )
            query_results["job_number"] = num
            query_results["steps_count"] = len(steps)
            query_results["clarifications_count"] = len(clarifications)
            return "\n\n".join(context_parts), query_results

    # "last job" / "latest" / "recent"
    if any(kw in msg_lower for kw in ("last job", "latest", "recent", "laatste")):
        job = await conn.fetchrow(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 1"
        )
        if job:
            job_id = str(job["id"])
            job_d = _row_to_dict(job)
            steps = await conn.fetch(
                "SELECT * FROM job_steps WHERE job_id=$1 ORDER BY step_index", job_id
            )
            clarifications = await conn.fetch(
                "SELECT * FROM clarifications WHERE job_id=$1 ORDER BY asked_at DESC NULLS LAST",
                job_id,
            )
            context_parts.append(
                "=== Last job ===\n" + json.dumps(job_d, default=_json_default, indent=2)
            )
            context_parts.append(
                "=== Job steps ===\n"
                + json.dumps([_row_to_dict(s) for s in steps], default=_json_default, indent=2)
            )
            context_parts.append(
                "=== Clarifications ===\n"
                + json.dumps(
                    [_row_to_dict(c) for c in clarifications],
                    default=_json_default,
                    indent=2,
                )
            )
            query_results["last_job"] = True
            query_results["steps_count"] = len(steps)
            query_results["clarifications_count"] = len(clarifications)
            return "\n\n".join(context_parts), query_results

    # "failed jobs"
    if "failed" in msg_lower and ("job" in msg_lower or "jobs" in msg_lower):
        rows = await conn.fetch(
            "SELECT id, status, job_post, context, created_at, updated_at FROM jobs WHERE status=$1 ORDER BY created_at DESC LIMIT 10",
            "FAILED",
        )
        context_parts.append(
            "=== Failed jobs (up to 10) ===\n"
            + json.dumps([_row_to_dict(r) for r in rows], default=_json_default, indent=2)
        )
        query_results["failed_jobs_count"] = len(rows)
        return "\n\n".join(context_parts), query_results

    # "running jobs"
    if "running" in msg_lower and ("job" in msg_lower or "jobs" in msg_lower):
        rows = await conn.fetch(
            "SELECT id, status, job_post, context, created_at, updated_at FROM jobs WHERE status=$1 ORDER BY created_at DESC LIMIT 10",
            "RUNNING",
        )
        context_parts.append(
            "=== Running jobs (up to 10) ===\n"
            + json.dumps([_row_to_dict(r) for r in rows], default=_json_default, indent=2)
        )
        query_results["running_jobs_count"] = len(rows)
        return "\n\n".join(context_parts), query_results

    # agents / hired
    if any(kw in msg_lower for kw in ("agent", "agents", "hired")):
        rows = await conn.fetch(
            "SELECT id, agent_id, name, role, specialization, status, performance_score FROM hired_agents ORDER BY hired_at DESC NULLS LAST LIMIT 20"
        )
        context_parts.append(
            "=== Hired agents (up to 20) ===\n"
            + json.dumps([_row_to_dict(r) for r in rows], default=_json_default, indent=2)
        )
        query_results["hired_agents_count"] = len(rows)
        return "\n\n".join(context_parts), query_results

    # system status / health
    if any(kw in msg_lower for kw in ("status", "health", "system", "recent jobs")):
        rows = await conn.fetch(
            "SELECT id, status, job_post, created_at, updated_at FROM jobs ORDER BY created_at DESC LIMIT 20"
        )
        context_parts.append(
            "=== Recent jobs (20) ===\n"
            + json.dumps([_row_to_dict(r) for r in rows], default=_json_default, indent=2)
        )
        query_results["recent_jobs_count"] = len(rows)
        return "\n\n".join(context_parts), query_results

    return "", query_results


@router.post("/chat")
async def debug_chat(req: DebugChatRequest):
    """
    AI debug assistant that can query the database and diagnose issues.
    """
    try:
        pool = await get_db()
    except Exception as e:
        logger.exception("get_db failed in debug_chat")
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        try:
            db_context, query_results = await _gather_context(conn, req.message)
        except Exception as e:
            logger.exception("_gather_context failed")
            raise HTTPException(status_code=500, detail="Failed to gather context")

    # Build user content for Claude
    user_content = req.message
    if db_context:
        user_content += "\n\n--- Database context ---\n" + db_context
    if req.conversation_history:
        last_n = req.conversation_history[-10:]
        conv_text = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')[:500]}"
            for m in last_n
        )
        user_content += "\n\n--- Conversation so far ---\n" + conv_text

    system_prompt = (
        "You are a technical debug assistant for the Wonderz AI content bureau platform. "
        "You have access to database query results. Give concrete technical diagnoses, not surface-level summaries. "
        "When analyzing jobs, check: status transitions, step outputs, error messages in context, token usage, timing. "
        "Respond in the same language as the user."
    )

    try:
        client = Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        text = response.content[0].text if response.content else ""
    except Exception as e:
        logger.exception("Claude API failed in debug_chat")
        raise HTTPException(
            status_code=500,
            detail="AI service error",
        )

    return {"response": text, "query_results": query_results}
