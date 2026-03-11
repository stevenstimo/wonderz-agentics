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


def _parse_context(ctx: Any) -> dict:
    if ctx is None:
        return {}
    if isinstance(ctx, dict):
        return ctx
    if isinstance(ctx, str):
        try:
            return json.loads(ctx)
        except json.JSONDecodeError:
            return {}
    return {}


def _format_job_context(job: dict, steps: list, clarifications: list) -> str:
    """Build a clear db_context string for Claude from job, steps, clarifications."""
    jni = job.get("job_number_int")
    job_number = f"{jni:04d}" if jni is not None else "?"
    ctx = _parse_context(job.get("context"))
    step_details = ""
    for s in steps:
        output = s.get("output")
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                output = {}
        output = output or {}
        step_details += f"  Step {s.get('step_index', '?')} ({s.get('agent_role', '?')}): {s.get('status', '?')}"
        step_details += f" | tokens: {s.get('tokens_used', 0)} | timing: {s.get('timing_ms') or 0}ms\n"
        if output.get("error"):
            step_details += f"    ERROR: {output['error']}\n"
        if output.get("image_url"):
            step_details += f"    image_url: {output['image_url']}\n"
        if output.get("content"):
            content_preview = str(output["content"])[:100]
            step_details += f"    content: {content_preview}...\n"
    clarification_details = "\n".join(
        f"  - {_row_to_dict(c).get('question', '')[:80]}..." for c in clarifications
    ) if clarifications else "  (none)"
    return f"""
JOB #{job_number} (UUID: {job.get('id')})
Status: {job.get('status')}
Job post: {job.get('job_post', '')[:200]}...
Created: {job.get('created_at')}
Tokens used: {job.get('tokens_used', 0)}

Context highlights:
- image_url: {ctx.get('image_url', 'none')}
- final_content length: {len(str(ctx.get('final_content', '')))} chars
- chat_history: {len(ctx.get('chat_history', []))} messages
- user_feedback: {ctx.get('user_feedback', 'none')}
- execution_error: {ctx.get('execution_error', 'none')}

Steps ({len(steps)} total):
{step_details}

Clarifications ({len(clarifications)} total):
{clarification_details}
"""


def _debug_log(data: dict) -> None:
    import os
    log_path = os.environ.get("DEBUG_LOG_PATH", "/home/exedev/wonderz-agentics/.cursor/debug-43707b.log")
    try:
        import json as _j
        with open(log_path, "a") as f:
            f.write(_j.dumps({"sessionId": "43707b", "timestamp": __import__("time").time() * 1000, "location": "debug_chat.py:_gather_context", "message": "debug", "data": data}) + "\n")
    except Exception:
        pass


async def _gather_context(conn, message: str) -> tuple[dict, dict]:
    """
    Parse user message and run relevant DB queries.
    Returns (context_dict for prompt, query_results summary).
    """
    msg_lower = message.strip().lower()
    context_parts = []
    query_results = {}

    uuid_match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        message,
    )

    # UUID: single job by id
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
            db_context = _format_job_context(job_d, [_row_to_dict(s) for s in steps], clarifications)
            query_results["job_id"] = job_id
            query_results["steps_count"] = len(steps)
            query_results["clarifications_count"] = len(clarifications)
            return db_context, query_results

    # #NNNN: job by job_number_int (supports #126, #0126, etc.)
    number_match = re.search(r"#(\d{1,6})", message)
    if number_match:
        job_number_int = int(number_match.group(1))
        job = await conn.fetchrow(
            "SELECT * FROM jobs WHERE job_number_int = $1 ORDER BY created_at DESC LIMIT 1",
            job_number_int,
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
            db_context = _format_job_context(job_d, [_row_to_dict(s) for s in steps], clarifications)
            query_results["job_number"] = f"{job_number_int:04d}"
            query_results["steps_count"] = len(steps)
            query_results["clarifications_count"] = len(clarifications)
            return db_context, query_results

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
            db_context = _format_job_context(job_d, [_row_to_dict(s) for s in steps], clarifications)
            query_results["last_job"] = True
            query_results["steps_count"] = len(steps)
            query_results["clarifications_count"] = len(clarifications)
            return db_context, query_results

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

    # agent X / agents by name or role
    agent_match = re.search(r"agent\s+(?:named\s+)?([a-zA-Z0-9_-]+)", msg_lower)
    if agent_match:
        search_term = agent_match.group(1)
        rows = await conn.fetch(
            "SELECT id, agent_id, name, role, specialization, status, performance_score FROM hired_agents WHERE name ILIKE $1 OR role ILIKE $1 ORDER BY hired_at DESC NULLS LAST LIMIT 20",
            f"%{search_term}%",
        )
        context_parts.append(
            "=== Hired agents (matching "
            + search_term
            + ") ===\n"
            + json.dumps([_row_to_dict(r) for r in rows], default=_json_default, indent=2)
        )
        query_results["hired_agents_count"] = len(rows)
        return "\n\n".join(context_parts), query_results

    # agents / hired (generic)
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

    # skills
    if "skill" in msg_lower or "skills" in msg_lower:
        try:
            rows = await conn.fetch(
                "SELECT skill_id, name, domain, usage_count FROM agent_skills ORDER BY usage_count DESC NULLS LAST LIMIT 50"
            )
        except Exception:
            rows = await conn.fetch(
                "SELECT skill_id, name, domain FROM agent_skills ORDER BY name LIMIT 50"
            )
        context_parts.append(
            "=== Skills (up to 50) ===\n"
            + json.dumps([_row_to_dict(r) for r in rows], default=_json_default, indent=2)
        )
        query_results["skills_count"] = len(rows)
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


def _agent_log(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    import json as _j
    try:
        with open("/home/exedev/wonderz-agentics/.cursor/debug-c78650.log", "a") as f:
            f.write(_j.dumps({"sessionId": "c78650", "location": location, "message": message, "data": data, "hypothesisId": hypothesis_id, "timestamp": __import__("time").time() * 1000}) + "\n")
    except Exception:
        pass


@router.post("/chat")
async def debug_chat(req: DebugChatRequest):
    """
    AI debug assistant that can query the database and diagnose issues.
    """
    # #region agent log
    _agent_log("debug_chat.py:entry", "request received", {"msgLen": len(req.message)}, "H2")
    # #endregion
    logger.info("debug_chat request received: %s", req.message[:80] + "..." if len(req.message) > 80 else req.message)
    try:
        pool = await get_db()
    except Exception as e:
        logger.exception("get_db failed in debug_chat")
        raise HTTPException(status_code=503, detail="Database unavailable")

    # #region agent log
    _agent_log("debug_chat.py:after_get_db", "pool acquired", {}, "H2")
    # #endregion
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
        "You have DIRECT access to the Wonderz database. When the user asks about a job, agent, or system status, "
        "you receive the actual database records. Analyze them technically — check status transitions, step outputs, "
        "errors, token usage, timing. Give concrete answers, not generic troubleshooting steps. "
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
        # #region agent log
        _agent_log("debug_chat.py:after_claude", "claude success", {"textLen": len(text)}, "H3")
        # #endregion
    except Exception as e:
        # #region agent log
        _agent_log("debug_chat.py:claude_error", "claude failed", {"err": str(e)[:200]}, "H3")
        # #endregion
        logger.exception("Claude API failed in debug_chat: %s", e)
        raise HTTPException(
            status_code=500,
            detail="AI service error",
        )

    # #region agent log
    _agent_log("debug_chat.py:return", "returning response", {"textLen": len(text)}, "H2")
    # #endregion
    return {"response": text, "query_results": query_results}
