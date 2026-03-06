import json
import logging
import os
import time
import uuid
from urllib.parse import quote
from typing import Any, Dict, List, Optional, Tuple

from app.db import init_db_pool
from app.database import get_db
from app.orchestration.intake_engine import IntakeEngine
from app.orchestration.strategy_room import StrategyRoom
from models.unified import JobStatus, ExecutionPlan

logger = logging.getLogger(__name__)

# Model for pipeline agent calls (copywriter, reviewer)
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


def _json_default(obj: Any) -> Any:
    """For json.dumps: handle non-JSON-serializable values (e.g. datetime)."""
    from datetime import date, datetime
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


async def _get_pool():
    pool = await init_db_pool()
    if not pool:
        logger.warning("DB pool not initialised - job pipeline skipped")
        return None
    return pool


def _coerce_context(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


async def _load_job(conn, job_id: str):
    job = await conn.fetchrow(
        "SELECT id, job_post, context, status, tokens_used FROM jobs WHERE id=$1",
        job_id,
    )
    if not job:
        raise ValueError(f"Job not found: {job_id}")
    return job


async def _update_job_context(conn, job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    row = await conn.fetchrow("SELECT context FROM jobs WHERE id=$1", job_id)
    current = _coerce_context(row.get("context") if row else None)
    current.update(updates)
    await conn.execute(
        "UPDATE jobs SET context=$1::jsonb, updated_at=now() WHERE id=$2",
        json.dumps(current, default=_json_default),
        job_id,
    )
    return current


async def _store_clarifications(conn, job_id: str, clarifications, round_number: int):
    for q in clarifications:
        await conn.execute(
            """
            INSERT INTO clarifications(job_id, question_id, question, asked_at, round_number)
            VALUES($1, $2, $3, now(), $4)
            ON CONFLICT (question_id)
            DO UPDATE SET question=$3, asked_at=now(), round_number=$4
            """,
            job_id,
            q.id,
            q.question,
            round_number,
        )


async def _next_clarification_round(conn, job_id: str) -> int:
    row = await conn.fetchrow(
        "SELECT COALESCE(MAX(round_number), 0) AS max_round FROM clarifications WHERE job_id=$1",
        job_id,
    )
    return (row.get("max_round") or 0) + 1


async def _fetch_available_agents(conn) -> List[str]:
    try:
        rows = await conn.fetch(
            "SELECT role FROM hired_agents WHERE status = 'active'"
        )
        return [r["role"] for r in rows if r.get("role")]
    except Exception as exc:
        logger.warning("Failed to load available agents: %s", exc)
        return []


def _brief_ctx(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract objective, language, tone, focus, word_count from job context.brief."""
    brief = context.get("brief") if isinstance(context.get("brief"), dict) else {}
    ctx = brief.get("context") if isinstance(brief.get("context"), dict) else {}
    return {
        "objective": ctx.get("objective") or brief.get("objective") or context.get("objective") or "",
        "language": ctx.get("language") or brief.get("language") or context.get("language") or "English",
        "tone": ctx.get("tone") or brief.get("tone") or context.get("tone") or "informative",
        "focus": ctx.get("focus") or brief.get("focus") or context.get("focus") or "general",
        "word_count": ctx.get("word_count") or brief.get("word_count") or context.get("word_count") or 400,
    }


def _build_image_prompt(context: Dict[str, Any]) -> str:
    """Build a descriptive English image prompt from job context for Pollinations.ai."""
    objective = context.get("objective", "") or ""
    brief_ctx = _brief_ctx(context)
    objective = brief_ctx.get("objective") or objective
    focus = brief_ctx.get("focus") or "general"
    tone = brief_ctx.get("tone") or "informative"
    prompt = f"Professional blog illustration for article about {objective or 'content'}"
    if focus and focus != "general":
        prompt += f", focusing on {focus}"
    if tone:
        prompt += f", {tone} style"
    prompt += ", high quality, editorial photography style, vibrant colors"
    return prompt


def _run_step_agent(
    agent_role: str,
    step_name: str,
    context: Dict[str, Any],
    previous_content: Optional[str],
) -> Tuple[Dict[str, Any], int]:
    """
    Run one pipeline step: copywriter (Claude), reviewer (Claude), image_generator (placeholder), or generic Claude.
    Returns (output_dict, tokens_used).
    """
    role_lower = (agent_role or "").lower()
    step_desc = step_name or agent_role or "step"
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; using placeholder for step %s", step_desc)
        return (
            {"status": "placeholder", "content": f"[Placeholder – {step_desc}. No API key.]", "agent_role": agent_role},
            0,
        )

    try:
        from anthropic import Anthropic
        client = Anthropic()
    except Exception as e:
        logger.warning("Anthropic client init failed: %s; using placeholder", e)
        return (
            {"status": "placeholder", "content": f"[Placeholder – {step_desc}. {e}]", "agent_role": agent_role},
            0,
        )

    brief_ctx = _brief_ctx(context)
    objective = brief_ctx.get("objective") or "content"
    language = str(brief_ctx.get("language") or "English")
    tone = str(brief_ctx.get("tone") or "informative")
    focus = str(brief_ctx.get("focus") or "general")
    word_count = brief_ctx.get("word_count")
    if word_count is None:
        word_count = 400
    try:
        word_count = int(word_count)
    except (TypeError, ValueError):
        word_count = 400

    # Copywriter: write main content
    if role_lower in ("copywriter", "copy writer"):
        system = f"You are a professional copywriter. Write in {language}. Tone: {tone}. Focus: {focus}. Output only the requested content, no meta-commentary. You MUST respect the required word count: the final text must be approximately {word_count} words (strict requirement)."
        user = f"Write an article of approximately {word_count} words about: {objective}"
        user_feedback = context.get("user_feedback") or context.get("feedback") or ""
        if user_feedback and isinstance(user_feedback, str):
            user += f"\n\nUser feedback (apply this): {user_feedback}"
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = (response.content[0].text if response.content else "").strip()
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            return ({"status": "completed", "content": text, "agent_role": agent_role, "step_name": step_desc}, tokens)
        except Exception as e:
            logger.exception("Copywriter step failed: %s", e)
            return ({"status": "failed", "content": "", "error": str(e), "agent_role": agent_role}, 0)

    # Reviewer: review previous content
    if role_lower in ("reviewer", "review"):
        if not previous_content:
            return ({"status": "skipped", "review": "No content to review.", "approved": True, "agent_role": agent_role}, 0)
        system = "You are a content reviewer. Check quality, grammar, and tone consistency. Reply in the same language as the content. Keep the reply concise. End with APPROVED or CHANGES NEEDED."
        user = f"Review this content:\n\n{previous_content[:12000]}"
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            review_text = (response.content[0].text if response.content else "").strip()
            approved = "approved" in review_text.lower() or "changes needed" not in review_text.lower()
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
            return (
                {"status": "completed", "review": review_text, "approved": approved, "agent_role": agent_role, "content": previous_content},
                tokens,
            )
        except Exception as e:
            logger.exception("Reviewer step failed: %s", e)
            return ({"status": "failed", "review": str(e), "approved": False, "agent_role": agent_role}, 0)

    # Image generator: Pollinations.ai (no API key)
    if role_lower in ("image_generator", "image generator", "imagegenerator"):
        prompt = _build_image_prompt(context)
        encoded = quote(prompt, safe="")
        image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=768&nologo=true"
        return (
            {
                "image_url": image_url,
                "image_status": "generated",
                "prompt": prompt,
                "agent_role": agent_role,
            },
            0,
        )

    # Generic: one Claude call
    system = f"You are a helpful assistant. Write in {language}. Tone: {tone}."
    user = f"Task: {step_desc}. Context: {objective}. Produce the requested output (no meta-commentary)."
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = (response.content[0].text if response.content else "").strip()
        tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
        return ({"status": "completed", "content": text, "agent_role": agent_role, "step_name": step_desc}, tokens)
    except Exception as e:
        logger.exception("Generic step failed: %s", e)
        return ({"status": "failed", "content": f"[Error: {e}]", "agent_role": agent_role}, 0)


async def _insert_plan_steps(conn, job_id: str, plan: ExecutionPlan):
    for step in plan.steps:
        step_id = str(uuid.uuid4())
        step_name = step.description or f"step_{step.step_index}"
        input_payload = {"description": step.description} if step.description else {}
        await conn.execute(
            """
            INSERT INTO job_steps (
                id,
                job_id,
                step_index,
                step_name,
                agent_role,
                unified_tool,
                status,
                input_payload,
                requires_approval,
                created_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,now())
            """,
            step_id,
            job_id,
            step.step_index,
            step_name,
            step.agent_role,
            step.unified_tool,
            "pending",
            json.dumps(input_payload, default=_json_default),
            step.requires_approval,
        )


async def run_intake_inline(job_id: str, job_post: str):
    """
    1. Call IntakeEngine.analyze_job_post(job_post)
    2. If brief.is_complete is False:
       - Store clarification questions in the clarifications table
       - Keep job status as INTAKE_CLARIFICATION
    3. If brief.is_complete is True:
       - Call StrategyRoom.generate_execution_plan(brief, available_agents)
       - Store the plan steps in job_steps table using ACTUAL column names:
         (id, job_id, step_index, step_name, agent_role, unified_tool, status, input_payload, requires_approval)
       - Update job status to PLAN_PROPOSED
       - Store the plan in jobs.context jsonb
    """
    pool = await _get_pool()
    if not pool:
        return

    intake = IntakeEngine()
    strategy = StrategyRoom()

    try:
        brief = intake.analyze_job_post(job_post)
        async with pool.acquire() as conn:
            await _update_job_context(
                conn,
                job_id,
                {
                    "brief": brief.model_dump(),
                    "previous_answers": {},
                },
            )

            if not brief.is_complete:
                await _store_clarifications(conn, job_id, brief.clarifications, round_number=1)
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.INTAKE_CLARIFICATION.value,
                    job_id,
                )
                return

            available_agents = await _fetch_available_agents(conn)
            plan = strategy.generate_execution_plan(brief, available_agents)
            await _insert_plan_steps(conn, job_id, plan)
            await _update_job_context(
                conn,
                job_id,
                {
                    "plan": plan.model_dump(),
                },
            )
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.PLAN_PROPOSED.value,
                job_id,
            )
    except Exception as exc:
        logger.error("run_intake_inline failed for job %s: %s", job_id, exc, exc_info=True)


async def run_intake_answers_inline(job_id: str, answers: dict):
    """
    1. Load existing job context; pass chat_history into IntakeEngine.
    2. If not complete → store clarifications, stay INTAKE_CLARIFICATION.
    3. If complete and context has final_content (revision) → set RUNNING, run_job_inline (skip StrategyRoom).
    4. Else (first-time complete) → StrategyRoom → PLAN_PROPOSED.
    """
    pool = await _get_pool()
    if not pool:
        return

    intake = IntakeEngine()
    strategy = StrategyRoom()
    run_revision = False

    try:
        async with pool.acquire() as conn:
            job = await _load_job(conn, job_id)
            context = _coerce_context(job.get("context"))
            previous_answers = context.get("previous_answers") or {}
            merged_answers = {**previous_answers, **(answers or {})}
            job_post = job.get("job_post") or context.get("job_post") or ""
            chat_history = list(context.get("chat_history") or [])

            brief = intake.analyze_job_post(
                job_post,
                previous_answers=merged_answers,
                chat_history=chat_history if chat_history else None,
            )
            chat_history = list(chat_history)
            chat_history.append({"role": "ceo", "content": brief.message or ""})
            await _update_job_context(
                conn,
                job_id,
                {
                    "brief": brief.model_dump(),
                    "previous_answers": merged_answers,
                    "chat_history": chat_history,
                },
            )

            if not brief.is_complete:
                round_number = await _next_clarification_round(conn, job_id)
                await _store_clarifications(conn, job_id, brief.clarifications, round_number=round_number)
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.INTAKE_CLARIFICATION.value,
                    job_id,
                )
                return

            if context.get("final_content"):
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.RUNNING.value,
                    job_id,
                )
                run_revision = True
            else:
                available_agents = await _fetch_available_agents(conn)
                plan = strategy.generate_execution_plan(brief, available_agents)
                await _insert_plan_steps(conn, job_id, plan)
                await _update_job_context(
                    conn,
                    job_id,
                    {
                        "plan": plan.model_dump(),
                    },
                )
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.PLAN_PROPOSED.value,
                    job_id,
                )
        if run_revision:
            await run_job_inline(job_id, None)
    except Exception as exc:
        logger.error("run_intake_answers_inline failed for job %s: %s", job_id, exc, exc_info=True)


async def run_job_inline(job_id: str, context_extra: Optional[dict] = None):
    """
    1. Load job and job_steps; merge context from DB with context_extra (e.g. user feedback).
    2. For each step: run agent, store output, update tokens.
    3. After all steps complete: set status to JOB_READY.
    """
    pool = await _get_pool()
    if not pool:
        return

    steps_completed = False
    try:
        async with pool.acquire() as conn:
            job = await _load_job(conn, job_id)
            context = _coerce_context(job.get("context"))
            if context_extra:
                context = {**context, **context_extra}

            steps = await conn.fetch(
                "SELECT id, step_index, step_name, agent_role, unified_tool FROM job_steps WHERE job_id=$1 ORDER BY step_index",
                job_id,
            )
            num_steps = len(steps)
            logger.info("run_job_inline: job %s with %s steps", job_id, num_steps)

            last_content: Optional[str] = None
            previous_content: Optional[str] = None
            for idx, step in enumerate(steps):
                step_id = step["id"]
                await conn.execute(
                    "UPDATE job_steps SET status='running', started_at=now() WHERE id=$1",
                    step_id,
                )

                started = time.monotonic()
                logger.info(
                    "Running job step %s for job %s (%s)",
                    step.get("step_name"),
                    job_id,
                    step.get("agent_role"),
                )
                step_name = step.get("step_name") or step.get("agent_role") or "step"
                agent_role = step.get("agent_role") or ""

                output, tokens_used = _run_step_agent(
                    agent_role=agent_role,
                    step_name=step_name,
                    context=context or {},
                    previous_content=previous_content,
                )
                output["step_name"] = step.get("step_name")
                output["agent_role"] = step.get("agent_role")
                output["unified_tool"] = step.get("unified_tool")

                if output.get("content"):
                    last_content = output["content"]
                    previous_content = output["content"]
                elif output.get("review") and previous_content:
                    last_content = previous_content

                timing_ms = int((time.monotonic() - started) * 1000)

                await conn.execute(
                    """
                    UPDATE job_steps
                    SET status='completed', completed_at=now(), output=$1::jsonb, tokens_used=$2, timing_ms=$3
                    WHERE id=$4
                    """,
                    json.dumps(output, default=_json_default),
                    tokens_used,
                    timing_ms,
                    step_id,
                )

                await conn.execute(
                    "UPDATE jobs SET tokens_used=COALESCE(tokens_used, 0) + $1, updated_at=now() WHERE id=$2",
                    tokens_used,
                    job_id,
                )
                if output.get("image_url"):
                    await _update_job_context(conn, job_id, {"image_url": output["image_url"]})
                logger.info("run_job_inline: job %s step %s of %s done", job_id, idx + 1, num_steps)

            steps_completed = True
            job_id_str = str(job_id)
            logger.info("All steps done for job %s. Setting JOB_READY...", job_id_str)
            try:
                pool_ready = await get_db()
                async with pool_ready.acquire() as conn:
                    logger.info("Storing final_content for job %s", job_id_str)
                    await _update_job_context(conn, job_id_str, {"final_content": last_content or "No content produced"})
                    logger.info("Updating status to JOB_READY for job %s", job_id_str)
                    result = await conn.execute(
                        "UPDATE jobs SET status='JOB_READY', updated_at=now() WHERE id=$1",
                        job_id_str,
                    )
                    logger.info("JOB_READY update result for job %s: %s", job_id_str, result)
            except Exception as e:
                logger.error("CRITICAL: Failed to set JOB_READY for job %s: %s", job_id_str, e, exc_info=True)
                raise
    except Exception as exc:
        logger.error(
            "run_job_inline failed for job %s: %s: %s",
            job_id,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        if steps_completed:
            try:
                async with pool.acquire() as conn_recovery:
                    await conn_recovery.execute(
                        "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                        JobStatus.JOB_READY.value,
                        job_id,
                    )
                logger.info("Job %s set to JOB_READY in recovery", job_id)
            except Exception as final_exc:
                logger.warning("Failed to set JOB_READY in recovery for job %s: %s", job_id, final_exc)
