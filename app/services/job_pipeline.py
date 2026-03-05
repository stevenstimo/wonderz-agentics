import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from app.db import init_db_pool
from app.orchestration.intake_engine import IntakeEngine
from app.orchestration.strategy_room import StrategyRoom
from models.unified import JobStatus, ExecutionPlan

logger = logging.getLogger(__name__)


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
    1. Load existing job context from jobs table
    2. Call IntakeEngine.analyze_job_post(job_post, previous_answers=answers)
    3. Same logic as above: if complete → StrategyRoom → PLAN_PROPOSED
       If not complete → store new clarifications → stay INTAKE_CLARIFICATION
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
            previous_answers = context.get("previous_answers") or {}
            merged_answers = {**previous_answers, **(answers or {})}
            job_post = job.get("job_post") or context.get("job_post") or ""

            brief = intake.analyze_job_post(job_post, previous_answers=merged_answers)
            await _update_job_context(
                conn,
                job_id,
                {
                    "brief": brief.model_dump(),
                    "previous_answers": merged_answers,
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
        logger.error("run_intake_answers_inline failed for job %s: %s", job_id, exc, exc_info=True)


async def run_job_inline(job_id: str, context: dict):
    """
    1. Load job_steps for this job_id
    2. For each step in order:
       - Update step status to 'running', set started_at
       - Execute the step (for now, just log it and create a placeholder output)
       - Update step status to 'completed', set completed_at, store output
       - Update jobs.tokens_used
    3. After all steps complete:
       - Update job status to JOB_READY
    """
    pool = await _get_pool()
    if not pool:
        return

    try:
        async with pool.acquire() as conn:
            steps = await conn.fetch(
                "SELECT id, step_index, step_name, agent_role, unified_tool FROM job_steps WHERE job_id=$1 ORDER BY step_index",
                job_id,
            )

            for step in steps:
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
                output = {
                    "status": "placeholder",
                    "step_name": step.get("step_name"),
                    "agent_role": step.get("agent_role"),
                    "unified_tool": step.get("unified_tool"),
                    "context": context or {},
                }
                timing_ms = int((time.monotonic() - started) * 1000)
                tokens_used = 0

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

            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.JOB_READY.value,
                job_id,
            )
    except Exception as exc:
        logger.error("run_job_inline failed for job %s: %s", job_id, exc, exc_info=True)
