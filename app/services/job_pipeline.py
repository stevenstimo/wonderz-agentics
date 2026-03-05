import json
import logging


def _json_default(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
import time
import uuid
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from app.db import init_db_pool
from app.orchestration.intake_engine import IntakeEngine
from app.orchestration.strategy_room import StrategyRoom
from models.unified import JobStatus, ExecutionPlan, StrategicBrief

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


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
        "UPDATE jobs SET context=$1, updated_at=now() WHERE id=$2",
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
            input_payload,
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
        ceo_message = (brief.message or "").strip()
        chat_history = [{"role": "ceo", "content": ceo_message}]
        async with pool.acquire() as conn:
            await _update_job_context(
                conn,
                job_id,
                {
                    "brief": brief.model_dump(),
                    "previous_answers": {},
                    "ceo_message": ceo_message,
                    "chat_history": chat_history,
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


async def run_intake_answers_inline(
    job_id: str,
    answers: Optional[dict] = None,
    user_message: Optional[str] = None,
):
    """
    1. Load job and context (chat_history, previous_answers).
    2. If user_message: append user turn to chat_history, call IntakeEngine with chat_history.
       If answers: merge into previous_answers, optionally append one user turn to chat_history, call with previous_answers.
    3. Append CEO reply to chat_history; persist context. If complete → StrategyRoom → PLAN_PROPOSED; else stay INTAKE_CLARIFICATION.
    """
    pool = await _get_pool()
    if not pool:
        return

    intake = IntakeEngine()
    strategy = StrategyRoom()

    try:
        async with pool.acquire() as conn:
            job = await _load_job(conn, job_id)
            context = _coerce_context(job.get("context"))
            chat_history = list(context.get("chat_history") or [])
            previous_answers = context.get("previous_answers") or {}
            job_post = job.get("job_post") or context.get("job_post") or ""

            if user_message is not None:
                msg_stripped = (user_message or "").strip()
                if not msg_stripped:
                    nudge = "Kun je wat meer details geven over wat je nodig hebt?"
                    brief_raw = context.get("brief")
                    ctx_brief = (brief_raw.get("context") or {}) if isinstance(brief_raw, dict) else {}
                    lang = (ctx_brief.get("language") or "") if isinstance(ctx_brief, dict) else ""
                    if isinstance(lang, str) and "english" in lang.lower():
                        nudge = "Could you give a bit more detail about what you need?"
                    chat_history.append({"role": "ceo", "content": nudge})
                    await _update_job_context(conn, job_id, {"chat_history": chat_history, "ceo_message": nudge})
                    return
                approval_phrases = ("ok", "start", "ga maar", "go", "start maar")
                if msg_stripped.lower() in approval_phrases:
                    chat_history.append({"role": "user", "content": user_message})
                    ceo_ack = "Duidelijk! Ik zet het team aan het werk."
                    chat_history.append({"role": "ceo", "content": ceo_ack})
                    brief_dict = context.get("brief")
                    if isinstance(brief_dict, dict):
                        try:
                            brief = StrategicBrief(**{**brief_dict, "is_complete": True})
                            await _update_job_context(conn, job_id, {"chat_history": chat_history, "ceo_message": ceo_ack})
                            available_agents = await _fetch_available_agents(conn)
                            plan = strategy.generate_execution_plan(brief, available_agents)
                            await _insert_plan_steps(conn, job_id, plan)
                            await _update_job_context(conn, job_id, {"plan": plan.model_dump()})
                            await conn.execute("UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2", JobStatus.PLAN_PROPOSED.value, job_id)
                        except Exception:
                            pass
                    else:
                        await _update_job_context(conn, job_id, {"chat_history": chat_history, "ceo_message": ceo_ack})
                    return
                chat_history.append({"role": "user", "content": user_message})
                brief = intake.analyze_job_post(job_post, chat_history=chat_history)
            else:
                merged_answers = {**previous_answers, **(answers or {})}
                # Optionally append one user turn for consistency (e.g. concatenate answers)
                if merged_answers != previous_answers:
                    combined = " ".join(f"{k}: {v}" for k, v in merged_answers.items() if v)
                    if combined:
                        chat_history.append({"role": "user", "content": combined})
                brief = intake.analyze_job_post(job_post, previous_answers=merged_answers)
                previous_answers = merged_answers

            ceo_message = brief.message or ""
            chat_history.append({"role": "ceo", "content": ceo_message})

            updates = {
                "brief": brief.model_dump(),
                "ceo_message": ceo_message,
                "chat_history": chat_history,
            }
            if user_message is None:
                updates["previous_answers"] = previous_answers

            await _update_job_context(conn, job_id, updates)

            if not brief.is_complete:
                round_number = await _next_clarification_round(conn, job_id)
                await _store_clarifications(conn, job_id, brief.clarifications, round_number=round_number)
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
                {"plan": plan.model_dump()},
            )
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.PLAN_PROPOSED.value,
                job_id,
            )
    except Exception as exc:
        logger.error("run_intake_answers_inline failed for job %s: %s", job_id, exc, exc_info=True)


def _get_brief_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract objective, language, tone, focus, word_count from job context/brief."""
    brief = context.get("brief") if isinstance(context.get("brief"), dict) else {}
    ctx = brief.get("context", {}) if isinstance(brief.get("context"), dict) else {}
    return {
        "objective": ctx.get("objective") or context.get("objective") or "",
        "language": ctx.get("language") or context.get("language") or "English",
        "tone": ctx.get("tone") or context.get("tone") or "informative",
        "focus": ctx.get("focus") or context.get("focus") or "general",
        "word_count": ctx.get("word_count") or context.get("word_count"),
        "includes_image": ctx.get("includes_image") or context.get("includes_image") or False,
    }


async def _get_previous_step_content(conn, job_id: str, before_step_index: int) -> str:
    """Get content from the most recent content-producing step before the given index."""
    rows = await conn.fetch(
        """SELECT output FROM job_steps WHERE job_id=$1 AND step_index < $2 AND status='completed' ORDER BY step_index DESC""",
        job_id,
        before_step_index,
    )
    for row in rows:
        out = row.get("output") or {}
        if isinstance(out, dict):
            if out.get("content"):
                return out["content"]
            if out.get("optimized_content"):
                return out["optimized_content"]
    return ""


async def run_job_inline(job_id: str, context: dict):
    """
    Execute job steps with Claude: copywriter writes content, reviewer reviews, seo optimizes.
    Image steps get a placeholder. On failure set step and job to failed.
    After all steps: store final_content in context, insert artifact, set JOB_READY.
    """
    pool = await _get_pool()
    if not pool:
        return

    client = Anthropic()
    try:
        async with pool.acquire() as conn:
            job = await _load_job(conn, job_id)
            job_post = job.get("job_post") or ""
            ctx = _coerce_context(job.get("context"))
            ctx.update(context or {})
            brief_ctx = _get_brief_context(ctx)
            language = brief_ctx.get("language") or "English"
            tone = brief_ctx.get("tone") or "informative"
            focus = brief_ctx.get("focus") or "general"
            word_count = brief_ctx.get("word_count")
            wc_str = f" Approximate length: {word_count} words." if word_count else ""

            steps = await conn.fetch(
                """SELECT id, step_index, step_name, agent_role, unified_tool FROM job_steps WHERE job_id=$1 ORDER BY step_index""",
                job_id,
            )

            last_content = ""
            for step in steps:
                step_id = step["id"]
                step_index = step["step_index"]
                agent_role = (step.get("agent_role") or "").lower()
                step_name = step.get("step_name") or ""

                await conn.execute(
                    "UPDATE job_steps SET status='running', started_at=now() WHERE id=$1",
                    step_id,
                )
                started = time.monotonic()
                tokens_used = 0
                output = {}

                try:
                    if agent_role in ("image", "image_generator", "image_generation"):
                        output = {
                            "image_status": "placeholder",
                            "note": "Image generation will be integrated with Pollinations.ai",
                        }
                    elif agent_role == "copywriter":
                        system = f"You are a professional copywriter. Write in {language}. Tone: {tone}. Focus: {focus}."
                        user = f"Job request: {job_post}\n\nObjective: {brief_ctx.get('objective', '')}{wc_str}\n\nWrite the full content below."
                        resp = client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=4000,
                            system=system,
                            messages=[{"role": "user", "content": user}],
                        )
                        text = resp.content[0].text
                        tokens_used = resp.usage.input_tokens + resp.usage.output_tokens
                        output = {"content": text}
                        last_content = text
                    elif agent_role == "reviewer":
                        content = await _get_previous_step_content(conn, job_id, step_index)
                        system = "You are a content reviewer. Check for quality, grammar, tone consistency, and alignment with the brief. Respond with a short review, whether you approve (true/false), and any suggestions."
                        user = f"Content to review:\n\n{content}"
                        resp = client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=2000,
                            system=system,
                            messages=[{"role": "user", "content": user}],
                        )
                        text = resp.content[0].text
                        tokens_used = resp.usage.input_tokens + resp.usage.output_tokens
                        approved = "approve" in text.lower() or "true" in text.lower()
                        output = {"review": text, "approved": approved, "suggestions": text}
                    elif agent_role in ("seo", "seo_specialist"):
                        content = await _get_previous_step_content(conn, job_id, step_index)
                        system = "You are an SEO specialist. Optimize the content for search engines. Return the optimized content, a short meta description, and a list of keywords."
                        user = f"Content to optimize:\n\n{content}"
                        resp = client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=4000,
                            system=system,
                            messages=[{"role": "user", "content": user}],
                        )
                        text = resp.content[0].text
                        tokens_used = resp.usage.input_tokens + resp.usage.output_tokens
                        output = {"optimized_content": text, "meta_description": text[:160], "keywords": []}
                        last_content = text
                    else:
                        system = f"You are a professional content agent. Task: {step_name}. Use language: {language}."
                        user = f"Job: {job_post}\n\nObjective: {brief_ctx.get('objective', '')}\n\nComplete the step."
                        resp = client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=4000,
                            system=system,
                            messages=[{"role": "user", "content": user}],
                        )
                        text = resp.content[0].text
                        tokens_used = resp.usage.input_tokens + resp.usage.output_tokens
                        output = {"content": text, "result": text}
                        if "content" in output:
                            last_content = text

                    timing_ms = int((time.monotonic() - started) * 1000)
                    await conn.execute(
                        """UPDATE job_steps SET status='completed', completed_at=now(), output=$1, tokens_used=$2, timing_ms=$3 WHERE id=$4""",
                        output,
                        tokens_used,
                        timing_ms,
                        step_id,
                    )
                    await conn.execute(
                        "UPDATE jobs SET tokens_used=COALESCE(tokens_used, 0) + $1, updated_at=now() WHERE id=$2",
                        tokens_used,
                        job_id,
                    )
                except Exception as step_exc:
                    logger.error("Step %s failed for job %s: %s", step_index, job_id, step_exc, exc_info=True)
                    await conn.execute(
                        """UPDATE job_steps SET status='failed', completed_at=now(), output=$1 WHERE id=$2""",
                        {"error": str(step_exc)},
                        step_id,
                    )
                    await conn.execute(
                        "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                        JobStatus.FAILED.value,
                        job_id,
                    )
                    return

            if not last_content:
                last_content = "(No content generated)"
            await _update_job_context(conn, job_id, {"final_content": last_content})
            try:
                last_step_id = steps[-1]["id"] if steps else None
                await conn.execute(
                    """INSERT INTO artifacts (job_id, step_id, artifact_type, name, proposed_data)
                       VALUES ($1, $2, 'content', 'final_content', $3::jsonb)""",
                    job_id,
                    last_step_id,
                    json.dumps({"content": last_content}, default=_json_default),
                )
            except Exception as art_exc:
                logger.warning("Could not insert artifact (table may not exist): %s", art_exc)
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.JOB_READY.value,
                job_id,
            )
    except Exception as exc:
        logger.error("run_job_inline failed for job %s: %s", job_id, exc, exc_info=True)
        pool = await _get_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                        JobStatus.FAILED.value,
                        job_id,
                    )
            except Exception:
                pass
