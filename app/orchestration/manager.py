import os
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable
import asyncpg
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")


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

    async def _connect(self):
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        return await asyncpg.connect(self.database_url)

    async def write_job_step(self, conn: asyncpg.Connection, job_id: str, step_name: str, agent: str, status: str, log: dict = None):
        """Insert a job_steps row and return its id."""
        await conn.execute(
            """
            INSERT INTO job_steps(job_id, step_name, agent, status, log, started_at)
            VALUES($1, $2, $3, $4, $5, now())
            """,
            job_id, step_name, agent, status, log or {}
        )

    async def update_job_status(self, conn: asyncpg.Connection, job_id: str, status: str):
        await conn.execute(
            "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
            status,
            job_id,
        )

    async def append_artifact(self, conn: asyncpg.Connection, job_id: str, name: str, artifact_type: str, content: dict = None, content_text: str = None, storage_path: str = None):
        await conn.execute(
            """
            INSERT INTO artifacts(job_id, name, artifact_type, content, content_text, storage_path, created_at)
            VALUES($1,$2,$3,$4,$5,$6,now())
            """,
            job_id, name, artifact_type, content or {}, content_text, storage_path
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
        await self.update_job_status(conn, job_id, "AWAITING_APPROVAL")
        await self.write_job_step(conn, job_id, "awaiting_approval", "orchestrator", "paused", {"reason": reason})

    async def resume_from_approval(self, conn: asyncpg.Connection, job_id: str):
        await self.update_job_status(conn, job_id, "running")
        await self.write_job_step(conn, job_id, "resumed", "orchestrator", "in_progress", {"info": "resumed by operator"})

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

            await self.update_job_status(conn, job_id, "running")
            current_step = None
            steps = 0

            while steps < max_steps:
                next_agent = self.determine_next_step(current_step, ctx)
                if next_agent is None:
                    # Workflow finished
                    await self.update_job_status(conn, job_id, "completed")
                    await self.write_job_step(conn, job_id, "finished", "orchestrator", "success", {"info": "workflow completed"})
                    break

                if next_agent == "AWAITING_APPROVAL":
                    await self.pause_for_approval(conn, job_id, reason="Legal requires manual approval")
                    # stop the loop; a human must resume
                    break

                # Record step start
                await self.write_job_step(conn, job_id, next_agent, next_agent, "in_progress", {"input": ctx.data.get(next_agent)})

                # Call the agent via the injected runner
                try:
                    result = await maybe_await(self.agent_runner(next_agent, {"job_id": job_id, "store_id": store_id, "context": ctx.data}))
                except Exception as e:
                    # Log failure and mark job
                    await self.write_job_step(conn, job_id, next_agent, next_agent, "failed", {"error": str(e)})
                    await self.update_job_status(conn, job_id, "failed")
                    break

                # Persist agent output into shared context and DB
                ctx.update(next_agent, result)
                ctx.add_history(next_agent, result)
                await self.write_job_step(conn, job_id, next_agent, next_agent, "success", {"output_summary": summarize(result)})

                # Persist shared context as an artifact so subsequent agents (or the frontend) can read exact state
                try:
                    await self.append_artifact(conn, job_id, "shared_context", "json", content=ctx.data)
                except Exception:
                    # non-fatal: log and continue
                    pass

                # Optionally store any artifacts returned by agent
                if isinstance(result, dict) and result.get("artifacts"):
                    for art in result.get("artifacts"):
                        await self.append_artifact(conn, job_id, art.get("name"), art.get("type", "json"), art.get("content"), art.get("content_text"), art.get("storage_path"))

                # Advance
                current_step = next_agent
                steps += 1

        finally:
            await conn.close()


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
