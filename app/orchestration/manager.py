import os
import json
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable
import asyncpg
from datetime import datetime
from app.orchestration.intake_engine import IntakeEngine
from app.orchestration.strategy_room import StrategyRoom
from app.services.team_coordinator import TeamCoordinator
from app.services.error_recovery import ErrorRecovery
from app.services.agent_instruction_builder import instruction_builder, OutputFormat
from app.websocket.manager import manager as ws_manager
from models.unified import JobStatus, StrategicBrief, ExecutionPlan

DATABASE_URL = os.getenv("DATABASE_URL")
logger = logging.getLogger(__name__)

def _json_default(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)


@dataclass
class SharedContext:
    job_id: str
    store_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    history: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update(self, key: str, value: Any):
        self.data[key] = value

    def add_history(self, step: str, info: Any):
        self.history.setdefault(step, []).append({"ts": datetime.utcnow().isoformat(), "info": info})


class OperationsManager:
    """Central orchestrator that decides which agents to call and records progress to DB.

    It is intentionally decoupled from concrete agent implementations via an `agent_runner` callback:
    `agent_runner(agent_name: str, input: dict) -> dict`.
    """

    def __init__(self, agent_runner: Callable[[str, dict], dict], database_url: Optional[str] = None):
        self.agent_runner = agent_runner
        self.database_url = database_url or DATABASE_URL
        self.intake_engine = IntakeEngine()
        self.strategy_room = StrategyRoom()
        self._recovery: Optional[ErrorRecovery] = None

    # ============ Intake & Planning Flow ============

    async def start_intake_flow(self, job_id: str, job_post: str):
        """
        Start the intake flow for a new job.
        
        Sets status to INTAKE_CLARIFICATION if questions are needed,
        or PLAN_PROPOSED if the brief is complete.
        """
        brief = self.intake_engine.analyze_job_post(job_post)
        
        conn = await self._connect()
        try:
            # Store the brief in job context
            await self.store_job_context(conn, job_id, {
                "brief": brief.model_dump(),
                "previous_answers": {},
                "output_format": (brief.context or {}).get("output_format"),
            })

            if brief.is_complete:
                # Generate plan immediately
                await self.generate_and_propose_plan(job_id, brief)
                await self.update_job_status(conn, job_id, JobStatus.PLAN_PROPOSED.value)
            else:
                # Ask clarification questions
                await self.update_job_status(conn, job_id, JobStatus.INTAKE_CLARIFICATION.value)
                await self._store_clarifications(conn, job_id, brief.clarifications, round_number=1)
                await self.write_job_step(
                    conn,
                    job_id,
                    "intake",
                    "orchestrator",
                    "awaiting_user_input",
                    output={
                        "clarifications": [
                            {"id": q.id, "question": q.question}
                            for q in brief.clarifications
                        ]
                    }
                )
        finally:
            await conn.close()

    async def handle_user_answer(self, job_id: str, answers: Dict[str, str]):
        """
        User provides answers to clarification questions.
        
        Re-runs intake analysis with the new information.
        """
        conn = await self._connect()
        try:
            context = await self.get_job_context(conn, job_id)
            if not context:
                raise ValueError(f"Job {job_id} not found")

            job_post = context.get("job_post", "")
            previous_answers = context.get("previous_answers", {})

            # Update with new answers
            previous_answers.update(answers)

            # Re-run intake analysis
            brief = self.intake_engine.analyze_job_post(job_post, previous_answers)

            # Update context
            await self.store_job_context(conn, job_id, {
                "brief": brief.model_dump(),
                "previous_answers": previous_answers,
                "output_format": (brief.context or {}).get("output_format"),
            })

            if brief.is_complete:
                # Generate plan
                await self.generate_and_propose_plan(job_id, brief)
                await self.update_job_status(conn, job_id, JobStatus.PLAN_PROPOSED.value)
            else:
                # Ask next round of questions
                round_number = await self._next_clarification_round(conn, job_id)
                await self._store_clarifications(conn, job_id, brief.clarifications, round_number=round_number)
                await self.update_job_status(conn, job_id, JobStatus.INTAKE_CLARIFICATION.value)
                await self.write_job_step(
                    conn,
                    job_id,
                    "intake_round",
                    "orchestrator",
                    "awaiting_user_input",
                    output={
                        "clarifications": [
                            {"id": q.id, "question": q.question}
                            for q in brief.clarifications
                        ]
                    }
                )
        finally:
            await conn.close()

    async def generate_and_propose_plan(self, job_id: str, brief: StrategicBrief):
        """Generate an execution plan from a complete brief.
        
        Uses dynamic agent selection: reads hired_agents from DB and picks
        the best available agent per required role.
        """
        # Try dynamic plan with DB lookup first
        missing_agents = []
        try:
            # Try the shared pool first, then create a temporary one
            from app.db import _pool as db_pool
            if not db_pool and self.database_url:
                import asyncpg as _apg
                temp_pool = await _apg.create_pool(self.database_url, min_size=1, max_size=2)
                try:
                    plan, missing_agents = await self.strategy_room.generate_dynamic_plan(brief, temp_pool)
                finally:
                    await temp_pool.close()
            elif db_pool:
                plan, missing_agents = await self.strategy_room.generate_dynamic_plan(brief, db_pool)
            else:
                plan = self.strategy_room.generate_execution_plan(brief)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Dynamic plan failed, using sync fallback: {e}")
            plan = self.strategy_room.generate_execution_plan(brief)

        conn = await self._connect()
        try:
            await self.store_job_context(conn, job_id, {
                "plan": plan.model_dump()
            })

            await self.write_job_step(
                conn,
                job_id,
                "plan_generation",
                "orchestrator",
                "success",
                output={
                    "steps": [
                        {
                            "step_index": s.step_index,
                            "agent_role": s.agent_role,
                            "agent_id": s.agent_id,
                            "tool": s.unified_tool,
                            "description": s.description
                        }
                        for s in plan.steps
                    ],
                    "required_hires": plan.hired_agents,
                    "missing_agents": missing_agents
                }
            )
        finally:
            await conn.close()

    async def approve_plan(self, job_id: str):
        """User approves the proposed plan; ready to execute."""
        conn = await self._connect()
        try:
            await self.update_job_status(conn, job_id, JobStatus.RUNNING.value)
            await self.write_job_step(
                conn,
                job_id,
                "plan_approved",
                "orchestrator",
                "success",
                output={"info": "User approved the execution plan"}
            )
        finally:
            await conn.close()

    async def handle_job_feedback(self, job_id: str, feedback: str):
        """
        User provides feedback on the completed job result.
        
        Re-routes specific agents for retry if needed.
        """
        # This logic would determine which agent(s) need to retry
        # For now, we'll mark it for manual handling
        conn = await self._connect()
        try:
            await self.write_job_step(
                conn,
                job_id,
                "user_feedback",
                "orchestrator",
                "recorded",
                output={"feedback": feedback}
            )
        finally:
            await conn.close()

    # ============ Context Storage ============

    async def store_job_context(self, conn: asyncpg.Connection, job_id: str, data: Dict[str, Any]):
        """Store or update job context data (brief, plan, answers, etc.)."""
        existing = await self.get_job_context(conn, job_id)
        if isinstance(existing, dict):
            existing.update(data)
        else:
            existing = data

        await conn.execute(
            "UPDATE jobs SET context=$1, updated_at=now() WHERE id=$2",
            json.dumps(existing, default=_json_default),
            job_id
        )

    async def get_job_context(self, conn: asyncpg.Connection, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job context data."""
        row = await conn.fetchrow("SELECT context FROM jobs WHERE id=$1", job_id)
        if not row:
            return None
        raw = row.get("context")
        if not raw:
            return {}
        if isinstance(raw, str):
            return json.loads(raw)
        if isinstance(raw, dict):
            return raw
        return {}

    async def _connect(self):
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        return await asyncpg.connect(self.database_url)

    async def _get_recovery(self) -> Optional[ErrorRecovery]:
        if self._recovery is not None:
            return self._recovery
        try:
            from app.db import init_db_pool
            pool = await init_db_pool()
            if not pool:
                return None
            self._recovery = ErrorRecovery(pool)
            return self._recovery
        except Exception as e:
            logger.warning("Error recovery disabled: %s", e)
            return None

    async def write_job_step(
        self,
        conn: asyncpg.Connection,
        job_id: str,
        step_name: str,
        agent_role: str,
        status: str,
        input_payload: Optional[dict] = None,
        output: Optional[dict] = None,
        unified_tool: Optional[str] = None,
        requires_approval: bool = False,
        tokens_used: int = 0,
        timing_ms: int = 0
    ):
        """Insert a job_steps row and return its id."""
        step_index = await self._next_step_index(conn, job_id)
        row = await conn.fetchrow(
            """
            INSERT INTO job_steps(
                job_id,
                step_index,
                step_name,
                agent_role,
                unified_tool,
                status,
                input_payload,
                output,
                tokens_used,
                timing_ms,
                requires_approval,
                started_at
            )
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,now())
            RETURNING id
            """,
            job_id,
            step_index,
            step_name,
            agent_role,
            unified_tool,
            status,
            json.dumps(input_payload or {}, default=_json_default),
            json.dumps(output or {}, default=_json_default),
            tokens_used,
            timing_ms,
            requires_approval
        )
        await self._broadcast_job_snapshot(conn, job_id)
        return row["id"] if row else None

    async def update_job_status(self, conn: asyncpg.Connection, job_id: str, status: str):
        await conn.execute(
            "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
            status,
            job_id,
        )
        await self._broadcast_job_snapshot(conn, job_id)

    async def _broadcast_job_snapshot(self, conn: asyncpg.Connection, job_id: str) -> None:
        try:
            job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
            if not job:
                return

            clarifications = await conn.fetch(
                "SELECT * FROM clarifications WHERE job_id=$1 ORDER BY asked_at DESC",
                job_id,
            )
            steps = await conn.fetch(
                "SELECT * FROM job_steps WHERE job_id=$1 ORDER BY step_index",
                job_id,
            )
            artifacts = await conn.fetch(
                "SELECT * FROM artifacts WHERE job_id=$1 AND artifact_type != 'context' ORDER BY created_at DESC",
                job_id,
            )

            payload = {
                "job": dict(job),
                "clarifications": [dict(c) for c in clarifications],
                "steps": [dict(s) for s in steps],
                "artifacts": [dict(a) for a in artifacts],
            }
            await ws_manager.broadcast_job_update(job_id, payload)
        except Exception as exc:
            logger.debug("WebSocket broadcast skipped for job %s: %s", job_id, exc)

    async def append_artifact(
        self,
        conn: asyncpg.Connection,
        job_id: str,
        name: str,
        artifact_type: str,
        original_data: Optional[dict] = None,
        proposed_data: Optional[dict] = None,
        review_feedback: Optional[str] = None,
        storage_path: Optional[str] = None,
        step_id: Optional[str] = None
    ):
        await conn.execute(
            """
            INSERT INTO artifacts(
                job_id,
                step_id,
                artifact_type,
                name,
                original_data,
                proposed_data,
                review_feedback,
                storage_path,
                created_at
            )
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,now())
            """,
            job_id,
            step_id,
            artifact_type,
            name,
            json.dumps(original_data or {}, default=_json_default),
            json.dumps(proposed_data or {}, default=_json_default),
            review_feedback,
            storage_path
        )

    def determine_next_step(self, current_step: str, context: SharedContext) -> Optional[str]:
        """Decide the next agent to run based on the current_step and shared context.

        Returns the agent name or None when workflow is complete.
        """
        # Simple decision graph (can be replaced with rules/ML later)
        # Minimal, configurable decision graph for MVP focusing on Copy & Review
        if current_step is None or current_step == "init":
            if context.data.get("parallel_agents") and context.data.get("parallel_task"):
                return "team_parallel"
            return "copy_agent"

        # After copy, send to reviewer
        if current_step == "copy_agent":
            return "reviewer_agent"

        # After reviewer, decide next step depending on review outcome saved in context
        if current_step == "reviewer_agent":
            review_out = context.data.get("reviewer_agent") or {}
            status = None
            if isinstance(review_out, dict):
                status = review_out.get("status")

            # Workflow contract: approved review transitions to JOB_READY.
            if status == "APPROVED":
                return "JOB_READY"

            # If reviewer requests changes -> go back to copy for another draft
            if status in ("NEEDS_CHANGES", "REJECTED"):
                # implement a retry counter in context
                retries = context.metadata.get("retries", 0)
                if retries < 3:
                    context.metadata["retries"] = retries + 1
                    return "copy_agent"
                # too many retries -> require manual approval
                context.metadata["awaiting_manual_approval"] = True
                return "AWAITING_APPROVAL"

            # Default: finish
            return None

    async def pause_for_approval(self, conn: asyncpg.Connection, job_id: str, reason: str = None):
        """Set job status to AWAITING_APPROVAL and write a job_steps entry."""
        await self.update_job_status(conn, job_id, JobStatus.AWAITING_APPROVAL.value)
        await self.write_job_step(
            conn,
            job_id,
            "awaiting_approval",
            "orchestrator",
            "awaiting_approval",
            output={"reason": reason}
        )

    async def resume_from_approval(self, conn: asyncpg.Connection, job_id: str):
        await self.update_job_status(conn, job_id, JobStatus.RUNNING.value)
        await self.write_job_step(
            conn,
            job_id,
            "resumed",
            "orchestrator",
            "in_progress",
            output={"info": "resumed by operator"}
        )

    async def run_workflow(self, job_id: str, store_id: Optional[str], initial_payload: dict, max_steps: int = 50):
        """Run a full workflow for a job_id using agent_runner to execute agents.

        This method:
        - Maintains a SharedContext
        - Decides next agent via determine_next_step
        - Records job_steps and artifacts to DB so frontend sees progress
        - Honors AWAITING_APPROVAL (pauses)
        """
        conn = await self._connect()
        try:
            ctx = SharedContext(job_id=job_id, store_id=store_id)
            ctx.update("payload", initial_payload)

            # Load existing job context from DB so restarted jobs have their data
            existing_ctx = await self.get_job_context(conn, job_id)
            if existing_ctx:
                for k, v in existing_ctx.items():
                    if k not in ctx.data:
                        ctx.update(k, v)

            final_status = None
            await self.update_job_status(conn, job_id, JobStatus.RUNNING.value)
            current_step = None
            steps = 0
            recovery = await self._get_recovery()

            while steps < max_steps:
                next_agent = self.determine_next_step(current_step, ctx)
                if next_agent is None:
                    # No deterministic next step - pause for approval
                    await self.pause_for_approval(conn, job_id, reason="No deterministic next step")
                    break

                if next_agent == "JOB_READY":
                    await self.update_job_status(conn, job_id, JobStatus.JOB_READY.value)
                    final_status = JobStatus.JOB_READY.value
                    await self.write_job_step(
                        conn,
                        job_id,
                        "job_ready",
                        "orchestrator",
                        "success",
                        output={"info": "Workflow completed and awaiting user approval"}
                    )
                    break

                if next_agent == "AWAITING_APPROVAL":
                    await self.pause_for_approval(conn, job_id, reason="Legal requires manual approval")
                    final_status = JobStatus.AWAITING_APPROVAL.value
                    # stop the loop; a human must resume
                    break

                if next_agent == "team_parallel":
                    await self.write_job_step(
                        conn,
                        job_id,
                        "team_parallel",
                        "team_coordinator",
                        "in_progress",
                        input_payload={
                            "agents": ctx.data.get("parallel_agents"),
                            "task": ctx.data.get("parallel_task"),
                        },
                    )
                    try:
                        result = await self._run_team_parallel(job_id, ctx)
                    except Exception as e:
                        import logging as _log
                        _log.getLogger(__name__).exception(
                            "Unexpected error in team execution for job %s", job_id
                        )
                        await self.write_job_step(
                            conn,
                            job_id,
                            "team_parallel",
                            "team_coordinator",
                            "failed",
                            output={"error": str(e)},
                        )
                        await self.update_job_status(conn, job_id, JobStatus.FAILED.value)
                        final_status = JobStatus.FAILED.value
                        break

                    ctx.update("team_parallel", result)
                    ctx.add_history("team_parallel", result)
                    await self.write_job_step(
                        conn,
                        job_id,
                        "team_parallel",
                        "team_coordinator",
                        "success",
                        output={"output_summary": summarize(result)},
                    )

                    current_step = next_agent
                    steps += 1
                    continue

                # Record step start
                step_id = await self.write_job_step(
                    conn,
                    job_id,
                    next_agent,
                    next_agent,
                    "in_progress",
                    input_payload={"input": ctx.data.get(next_agent)}
                )

                # Call the agent via the injected runner
                try:
                    job_context = await self.get_job_context(conn, job_id)
                    output_format_str = (job_context or {}).get("output_format")
                    output_format = OutputFormat(output_format_str) if output_format_str else None

                    agent_id = next_agent
                    if agent_id and not str(agent_id).startswith("agent:"):
                        agent_id = f"agent:{agent_id}"

                    agent = None
                    base_prompt = None
                    if agent_id:
                        agent = await conn.fetchrow(
                            "SELECT system_prompt FROM hired_agents WHERE agent_id = $1",
                            agent_id
                        )
                        if agent:
                            base_prompt = agent["system_prompt"]

                    enhanced_prompt = None
                    if base_prompt:
                        enhanced_prompt = instruction_builder.build_prompt(
                            base_system_prompt=base_prompt,
                            output_format=output_format,
                            context={
                                "platform": (job_context or {}).get("platform"),
                                "audience": (job_context or {}).get("audience"),
                            },
                        )

                    async def _call_agent():
                        payload = {"job_id": job_id, "store_id": store_id, "context": ctx.data}
                        if enhanced_prompt:
                            payload["agent_config"] = {
                                "agent_id": agent_id,
                                "system_prompt": enhanced_prompt,
                            }
                        return await maybe_await(
                            self.agent_runner(
                                next_agent,
                                payload
                            )
                        )

                    if recovery:
                        async def _on_retry(attempt: int, exc: Exception):
                            if step_id:
                                await recovery.record_retry(step_id, str(exc))
                        result = await recovery.execute_with_retry(_call_agent, on_retry=_on_retry)
                    else:
                        result = await _call_agent()
                except Exception as e:
                    import logging as _log
                    _log.getLogger(__name__).exception("Unexpected error in workflow step %s for job %s", next_agent, job_id)
                    await self.write_job_step(
                        conn,
                        job_id,
                        next_agent,
                        next_agent,
                        "failed",
                        output={"error": str(e)}
                    )
                    if recovery:
                        await recovery.mark_job_for_retry(job_id, str(e))
                        await recovery.record_dead_letter(
                            job_id=job_id,
                            agent_id=next_agent,
                            error_message=str(e),
                            retry_count=recovery.max_retries - 1,
                        )
                        await self.update_job_status(conn, job_id, JobStatus.BLOCKED.value)
                        final_status = JobStatus.BLOCKED.value
                    else:
                        await self.update_job_status(conn, job_id, JobStatus.FAILED.value)
                        final_status = JobStatus.FAILED.value
                    break

                if output_format:
                    agent_output = None
                    if isinstance(result, dict):
                        agent_output = (
                            result.get("content")
                            or result.get("text")
                            or result.get("full_output")
                            or result.get("output")
                        )
                    elif isinstance(result, str):
                        agent_output = result

                    if agent_output:
                        is_valid, error = instruction_builder.validate_output(
                            agent_output,
                            output_format
                        )
                        if not is_valid:
                            logger.warning(f"Output format invalid: {error}")
                            # Optioneel: retry logic hier

                # --- Handle agent-level errors gracefully ---
                if isinstance(result, dict) and result.get("error"):
                    error_type = result.get("error_type", "unknown")
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        "Agent %s returned error for job %s: %s",
                        next_agent, job_id, result.get("summary", error_type),
                    )

                    if error_type == "rate_limit":
                        # Pause job, let Celery retry later
                        await self.write_job_step(
                            conn, job_id, next_agent, next_agent, "paused",
                            output=result,
                        )
                        await self.update_job_status(conn, job_id, "PAUSED")
                        final_status = "PAUSED"
                        break

                    if error_type == "token_budget_exceeded":
                        await self.write_job_step(
                            conn, job_id, next_agent, next_agent, "failed",
                            output=result,
                        )
                        await self.update_job_status(conn, job_id, JobStatus.FAILED.value)
                        final_status = JobStatus.FAILED.value
                        break

                    # Other errors: record and continue to next step
                    await self.write_job_step(
                        conn, job_id, next_agent, next_agent, "failed",
                        output=result,
                    )
                    # Don't break — let determine_next_step decide

                # Persist agent output into shared context and DB
                ctx.update(next_agent, result)
                ctx.add_history(next_agent, result)
                await self.write_job_step(
                    conn,
                    job_id,
                    next_agent,
                    next_agent,
                    "success",
                    output={"output_summary": summarize(result)}
                )

                # Persist shared context as an artifact so subsequent agents (or the frontend) can read exact state
                try:
                    await self.append_artifact(
                        conn,
                        job_id,
                        "shared_context",
                        "context",
                        proposed_data=ctx.data
                    )
                except Exception as e:
                    # non-fatal: log and continue
                    import logging
                    logging.getLogger(__name__).warning("Failed to persist shared_context artifact for job %s: %s", job_id, e)

                # Store any artifacts returned by agent
                if isinstance(result, dict) and result.get("artifacts"):
                    for art in result.get("artifacts"):
                        try:
                            await self.append_artifact(
                                conn,
                                job_id,
                                art.get("name"),
                                art.get("type", "json"),
                                original_data=art.get("original_data"),
                                proposed_data=art.get("proposed_data"),
                                review_feedback=art.get("review_feedback"),
                                storage_path=art.get("storage_path"),
                                step_id=art.get("step_id")
                            )
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).error("Failed to persist artifact '%s' for job %s: %s", art.get('name'), job_id, e)

                # Advance
                current_step = next_agent
                steps += 1

            if final_status == JobStatus.JOB_READY.value:
                await self._update_skill_success_rates(conn, job_id, was_successful=True)
                await self._record_skill_metrics(conn, job_id, success=True)
            elif final_status == JobStatus.FAILED.value:
                await self._update_skill_success_rates(conn, job_id, was_successful=False)
                await self._record_skill_metrics(conn, job_id, success=False)

        finally:
            await conn.close()

    async def _run_team_parallel(self, job_id: str, ctx: SharedContext) -> dict:
        agents = ctx.data.get("parallel_agents") or []
        task = ctx.data.get("parallel_task") or {}

        from app.db import _pool as db_pool, init_db_pool

        pool = db_pool
        temp_pool = None
        if not pool:
            pool = await init_db_pool()
        if not pool:
            pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=2)
            temp_pool = pool

        coordinator = TeamCoordinator(pool, agent_runner=self.agent_runner)
        try:
            return await coordinator.execute_parallel(job_id, agents, task)
        finally:
            if temp_pool:
                await temp_pool.close()

    async def _update_skill_success_rates(self, conn, job_id: str, was_successful: bool):
        """Update success rates voor skills die in deze job gebruikt zijn."""
        from app.services.skill_loader import SkillLoader

        try:
            skill_logs = await conn.fetch(
                """
                SELECT DISTINCT skill_id
                FROM skill_usage_log
                WHERE job_id = $1
                """,
                job_id
            )

            from app.db import db_pool
            loader = SkillLoader(db_pool)
            for log in skill_logs:
                await loader.update_skill_success(
                    skill_id=log["skill_id"],
                    was_successful=was_successful,
                    feedback=None
                )

            logger.info("Updated success rates for %s skills", len(skill_logs))
        except Exception as e:
            logger.error("Failed to update skill success rates: %s", e)

    async def _record_skill_metrics(self, conn, job_id: str, success: bool):
        """Record skill metrics for A/B validation."""
        try:
            retry_count = 0
            execution_time_ms = 0

            try:
                retry_count = await conn.fetchval(
                    "SELECT COALESCE(SUM(retry_count), 0) FROM job_steps WHERE job_id = $1",
                    job_id,
                )
            except Exception as exc:
                logger.debug("Retry count unavailable for job %s: %s", job_id, exc)

            try:
                execution_time_ms = await conn.fetchval(
                    "SELECT COALESCE(SUM(timing_ms), 0) FROM job_steps WHERE job_id = $1",
                    job_id,
                )
            except Exception as exc:
                logger.debug("Execution time unavailable for job %s: %s", job_id, exc)

            await conn.execute(
                """
                UPDATE skill_usage_log
                SET job_success = $1,
                    retry_count = $2,
                    execution_time_ms = $3
                WHERE job_id = $4
                """,
                success,
                retry_count or 0,
                execution_time_ms or 0,
                job_id,
            )
        except Exception as exc:
            logger.error("Failed to record skill metrics for job %s: %s", job_id, exc)

    async def _next_step_index(self, conn: asyncpg.Connection, job_id: str) -> int:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(step_index), 0) AS max_index FROM job_steps WHERE job_id=$1",
            job_id
        )
        return (row.get("max_index") or 0) + 1

    async def _next_clarification_round(self, conn: asyncpg.Connection, job_id: str) -> int:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(round_number), 0) AS max_round FROM clarifications WHERE job_id=$1",
            job_id
        )
        return (row.get("max_round") or 0) + 1

    async def _store_clarifications(self, conn: asyncpg.Connection, job_id: str, clarifications, round_number: int):
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
                round_number
            )


async def maybe_await(value):
    if asyncio.iscoroutine(value):
        return await value
    return value


def summarize(obj: Any) -> str:
    try:
        if isinstance(obj, dict):
            return obj.get("summary") or (str(obj)[:400])
        return str(obj)[:400]
    except Exception:
        return "(unserializable)"
