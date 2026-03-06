import os
import json
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable
import asyncpg
from datetime import datetime
from app.orchestration.intake_engine import IntakeEngine
from app.orchestration.strategy_room import StrategyRoom
from models.unified import JobStatus, StrategicBrief, ExecutionPlan

DATABASE_URL = os.getenv("DATABASE_URL")


def _json_default(obj: Any) -> Any:
    """For json.dumps: handle non-JSON-serializable values (e.g. datetime)."""
    from datetime import date, datetime
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


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
                "previous_answers": {}
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
                "previous_answers": previous_answers
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
        """Generate an execution plan from a complete brief."""
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
                            "tool": s.unified_tool,
                            "description": s.description
                        }
                        for s in plan.steps
                    ],
                    "required_hires": plan.hired_agents
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
        if existing:
            existing.update(data)
        else:
            existing = data

        await conn.execute(
            "UPDATE jobs SET context=$1::jsonb, updated_at=now() WHERE id=$2",
            json.dumps(existing, default=_json_default),
            job_id
        )

    async def get_job_context(self, conn: asyncpg.Connection, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job context data."""
        row = await conn.fetchrow("SELECT context FROM jobs WHERE id=$1", job_id)
        if not row:
            return None
        return row.get("context") or {}

    async def _connect(self):
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        return await asyncpg.connect(self.database_url)

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
        await conn.execute(
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
            VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9,$10,$11,now())
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

    async def update_job_status(self, conn: asyncpg.Connection, job_id: str, status: str):
        await conn.execute(
            "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
            status,
            job_id,
        )

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
            VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,$8,now())
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

            # If reviewer approved -> finish (or next production steps)
            if status == "APPROVED":
                return None

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

            await self.update_job_status(conn, job_id, JobStatus.RUNNING.value)
            current_step = None
            steps = 0

            while steps < max_steps:
                next_agent = self.determine_next_step(current_step, ctx)
                if next_agent is None:
                    # Workflow finished
                    await self.update_job_status(conn, job_id, JobStatus.COMPLETED.value)
                    await self.write_job_step(
                        conn,
                        job_id,
                        "finished",
                        "orchestrator",
                        "success",
                        output={"info": "workflow completed"}
                    )
                    break

                if next_agent == "AWAITING_APPROVAL":
                    await self.pause_for_approval(conn, job_id, reason="Legal requires manual approval")
                    # stop the loop; a human must resume
                    break

                # Record step start
                await self.write_job_step(
                    conn,
                    job_id,
                    next_agent,
                    next_agent,
                    "in_progress",
                    input_payload={"input": ctx.data.get(next_agent)}
                )

                # Call the agent via the injected runner
                try:
                    result = await maybe_await(self.agent_runner(next_agent, {"job_id": job_id, "store_id": store_id, "context": ctx.data}))
                except Exception as e:
                    # Log failure and mark job
                    await self.write_job_step(
                        conn,
                        job_id,
                        next_agent,
                        next_agent,
                        "failed",
                        output={"error": str(e)}
                    )
                    await self.update_job_status(conn, job_id, JobStatus.FAILED.value)
                    break

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
                except Exception:
                    # non-fatal: log and continue
                    pass

                # Optionally store any artifacts returned by agent
                if isinstance(result, dict) and result.get("artifacts"):
                    for art in result.get("artifacts"):
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

                # Advance
                current_step = next_agent
                steps += 1

        finally:
            await conn.close()

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
