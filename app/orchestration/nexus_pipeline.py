"""NEXUSPipeline — 7-phase CEO orchestrator with quality gates and token budget.

Traceability (pre-flight):
- Agent call: app/services/job_pipeline.py — _run_step_agent_with_timeout(agent_role, step_name, context, previous_content), _run_step_agent()
- TokenGuard: app/services/token_guard.py — class TokenGuard, register_usage(job_id, tokens_used, step_id=None)
- Job status: app/routes/jobs.py, app/services/job_pipeline.py — UPDATE jobs SET status=$1, updated_at=now()
- job_steps: app/services/job_pipeline.py — UPDATE job_steps SET status=..., output=..., tokens_used=..., timing_ms=...
- Pool: app/db.py init_db_pool(), app/database.py get_db()
- job_steps columns: id, job_id, step_index, step_name, agent_role, agent_id, status, input_payload, output, tokens_used, timing_ms, ...
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.orchestration.handoff_context import HandoffContext
from app.orchestration.quality_gate import QualityGate

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Token budget overschreden voor job {job_id}")


def _json_default(obj: Any) -> Any:
    from datetime import date, datetime
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class NEXUSPipeline:
    """
    7-fase CEO orchestrator pipeline.
    Elke fase is een aparte methode. HandoffContext verbindt de fasen.
    """

    MAX_RETRIES = 3
    quality_gate = QualityGate()

    def __init__(self) -> None:
        self._pool: Optional[Any] = None

    async def run(
        self,
        job_id: str,
        user_id: str,
        platform: str,
        job_post: str,
        token_budget: int = 50000,
        pool: Optional[Any] = None,
    ) -> HandoffContext:
        from app.db import init_db_pool
        self._pool = pool or await init_db_pool()
        if not self._pool:
            logger.warning("NEXUS: no DB pool, skipping pipeline for job %s", job_id)
            ctx = HandoffContext(job_id=job_id, user_id=user_id, platform=platform, token_budget=token_budget)
            ctx.error = "db_pool_unavailable"
            return ctx

        ctx = HandoffContext(
            job_id=job_id,
            user_id=user_id,
            platform=platform,
            token_budget=token_budget,
        )
        try:
            await self.phase_1_intake(ctx, job_post)
            await self.phase_2_planning(ctx)
            await self.phase_3_execution(ctx)
            await self.phase_4_qa_loop(ctx)
            await self.phase_5_ceo_review(ctx)
            await self.phase_6_approval_gate(ctx)
            await self.phase_7_deploy(ctx)
        except BudgetExceededError:
            ctx.error = "token_budget_exceeded"
            await self._update_job_status(ctx.job_id, "FAILED", ctx)
        except Exception as e:
            ctx.error = str(e)
            logger.error("Pipeline fout job %s: %s", job_id, e, exc_info=True)
            await self._update_job_status(ctx.job_id, "FAILED", ctx)
        return ctx

    async def phase_1_intake(self, ctx: HandoffContext, job_post: str) -> None:
        """Bouw StrategicBrief uit job_post. Status blijft RUNNING (we komen uit approve_plan)."""
        ctx.strategic_brief = {
            "objective": job_post,
            "platform": ctx.platform,
        }

    async def phase_2_planning(self, ctx: HandoffContext) -> None:
        """
        Laadt execution_plan uit job_steps tabel.
        Voegt GTM-step toe voor wonderz/clawagency/blogable als die nog niet aanwezig is.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id AS step_id, step_index, step_name, agent_role, agent_id, input_payload, status
                FROM job_steps
                WHERE job_id = $1
                ORDER BY step_index ASC
                """,
                ctx.job_id,
            )
        ctx.execution_plan = []
        for r in rows:
            payload = r.get("input_payload")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload) if payload else {}
                except json.JSONDecodeError:
                    payload = {}
            elif not isinstance(payload, dict):
                payload = {}
            step_id = str(r["step_id"]) if r.get("step_id") else None
            ctx.execution_plan.append({
                "step_id": step_id,
                "step_index": r.get("step_index", 0),
                "step_name": r.get("step_name") or f"step_{r.get('step_index', 0)}",
                "agent_role": r.get("agent_role") or "",
                "agent_id": r.get("agent_id"),
                "input_payload": payload,
                "status": r.get("status", "pending"),
            })

        GTM_PLATFORMS = {"wonderz", "clawagency", "blogable"}
        has_gtm = any(
            (s.get("agent_id") or (s.get("agent_role") or "").lower()) == "agent:gtm-specialist"
            or (s.get("agent_role") or "").lower() == "gtm-specialist"
            for s in ctx.execution_plan
        )
        if ctx.platform.lower() in GTM_PLATFORMS and not has_gtm:
            next_index = max((s.get("step_index", 0) for s in ctx.execution_plan), default=0) + 1
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO job_steps (job_id, agent_id, agent_role, step_name, step_index, status, input_payload)
                    VALUES ($1, $2, $3, $4, $5, 'pending', $6::jsonb)
                    RETURNING id
                    """,
                    ctx.job_id,
                    "agent:gtm-specialist",
                    "gtm-specialist",
                    "gtm_analysis",
                    next_index,
                    json.dumps({"platform": ctx.platform}),
                )
            gtm_step_id = str(row["id"]) if row and row.get("id") else None
            ctx.execution_plan.append({
                "step_id": gtm_step_id,
                "step_index": next_index,
                "step_name": "gtm_analysis",
                "agent_role": "gtm-specialist",
                "agent_id": "agent:gtm-specialist",
                "input_payload": {"platform": ctx.platform},
                "status": "pending",
            })
        # Status blijft RUNNING (gezet door approve_plan); phase_3 houdt RUNNING.

    async def phase_3_execution(self, ctx: HandoffContext) -> None:
        """Voer alle steps uit. Per step: agent aanroepen, output opslaan."""
        await self._update_job_status(ctx.job_id, "RUNNING", ctx)
        for step in ctx.execution_plan:
            await self._execute_step(ctx, step)

    async def phase_4_qa_loop(self, ctx: HandoffContext) -> None:
        """
        Dev↔QA loop: reviewer beoordeelt elke step-output.
        Bij NEEDS_CHANGES: stap opnieuw uitvoeren (max MAX_RETRIES).
        Bij 3x rejected: stap markeren als failed, doorgaan.
        """
        for step in ctx.execution_plan:
            step_name = step.get("step_name", "")
            output = ctx.step_outputs.get(step_name, "")
            passes = self.quality_gate.check(ctx, step_name, output)

            retry = 0
            while not passes and retry < self.MAX_RETRIES:
                if ctx.is_over_budget():
                    raise BudgetExceededError(ctx.job_id)
                logger.info(
                    "QA loop retry %s/%s voor %s", retry + 1, self.MAX_RETRIES, step_name
                )
                ctx.increment_retry(step_name)
                await self._execute_step(ctx, step)
                output = ctx.step_outputs.get(step_name, "")
                passes = self.quality_gate.check(ctx, step_name, output)
                retry += 1

            if not passes:
                logger.warning(
                    "Stap %s 3x rejected — doorgaan met laagste kwaliteit", step_name
                )

    async def phase_5_ceo_review(self, ctx: HandoffContext) -> None:
        """
        CEO beoordeelt eindresultaat tegen originele job post.
        Tevreden: doorgaan. Niet tevreden: agent terug via phase_4 (max 1 retry).
        Na 1 retry: proceed anyway met warning.
        """
        # 1. Laatste output (zelfde logica als phase_6)
        final_output = ""
        for step in reversed(ctx.execution_plan):
            step_name = step.get("step_name", "")
            output = ctx.step_outputs.get(step_name, "")
            if output and step_name != "gtm_analysis":
                final_output = output if isinstance(output, str) else str(output)
                break

        if not final_output:
            logger.info("Job %s phase_5: geen eindoutput — doorgaan zonder CEO review", ctx.job_id)
            return

        if ctx.is_over_budget():
            raise BudgetExceededError(ctx.job_id)
        if ctx.budget_warning():
            logger.warning("Job %s: token budget >80%% bij start CEO review", ctx.job_id)

        from app.services.job_pipeline import _coerce_context, _run_step_agent_with_timeout
        from app.services.token_guard import TokenGuard

        token_guard = TokenGuard(db_pool=self._pool)
        check = await token_guard.check_before_call(ctx.job_id, estimated_tokens=2000)
        if not check.get("allowed", True):
            raise BudgetExceededError(ctx.job_id)

        async with self._pool.acquire() as conn:
            job_row = await conn.fetchrow(
                "SELECT job_post, context FROM jobs WHERE id = $1",
                ctx.job_id,
            )
        job_context = _coerce_context(job_row.get("context") if job_row else None)
        job_post = (job_row.get("job_post") or "") if job_row else ""
        objective = (ctx.strategic_brief or {}).get("objective", job_post) or job_post

        agent_context = {
            "brief": ctx.strategic_brief,
            "objective": objective,
            "job_post": job_post,
            "platform": ctx.platform,
            "_knowledge_block": (job_context or {}).get("_knowledge_block", ""),
        }

        try:
            output_dict, tokens_used = await _run_step_agent_with_timeout(
                agent_role="reviewer",
                step_name="ceo_review",
                context=agent_context,
                previous_content=final_output[:12000],
            )
        except Exception as e:
            logger.error("Job %s CEO review call failed: %s", ctx.job_id, e, exc_info=True)
            logger.info("Job %s: doorgaan na CEO call fout", ctx.job_id)
            return

        ctx.register_tokens(tokens_used)
        try:
            await token_guard.register_usage(ctx.job_id, tokens_used, step_id=None)
        except Exception as e:
            logger.debug("TokenGuard register_usage (CEO review): %s", e)

        review_text = (output_dict.get("review") or output_dict.get("content") or "").strip()
        approved = output_dict.get("approved", False)
        if not approved and review_text:
            approved = "approved" in review_text.lower() and "changes needed" not in review_text.lower()

        if approved:
            logger.info("Job %s CEO review: APPROVED", ctx.job_id)
            return

        # NEEDS_REVISION
        ceo_retries = ctx.retry_counts.get("ceo_review", 0)
        if ceo_retries < 1:
            ctx.retry_counts["ceo_review"] = ceo_retries + 1
            logger.info(
                "Job %s CEO review: NEEDS_REVISION — retry %s/1 via phase_4",
                ctx.job_id,
                ctx.retry_counts["ceo_review"],
            )
            await self.phase_4_qa_loop(ctx)
            await self.phase_5_ceo_review(ctx)
            return

        logger.warning(
            "Job %s CEO review: NEEDS_REVISION na 1 retry — doorgaan zonder gebruiker te lastigvallen",
            ctx.job_id,
        )

    async def phase_6_approval_gate(self, ctx: HandoffContext) -> None:
        """
        Bepaalt de laatste content uit step_outputs.
        Schrijft die als final_content naar jobs.context.
        Zet status op JOB_READY.
        """
        final_content = ""
        for step in reversed(ctx.execution_plan):
            step_name = step.get("step_name", "")
            output = ctx.step_outputs.get(step_name, "")
            if output and step_name != "gtm_analysis":
                final_content = output if isinstance(output, str) else str(output)
                break
        await self._update_job_context(ctx.job_id, {
            "final_content": final_content,
            "quality_scores": ctx.quality_scores,
            "token_summary": {
                "used": ctx.token_used_total,
                "budget": ctx.token_budget,
            },
        })
        await self._update_job_status(ctx.job_id, "JOB_READY", ctx)

    async def phase_7_deploy(self, ctx: HandoffContext) -> None:
        """
        COMPLETED komt uit het approve-and-deploy endpoint — niet hier.
        Phase 7 logt alleen dat de pipeline klaar is.
        """
        logger.info("Job %s pipeline voltooid. Wacht op gebruikersapproval.", ctx.job_id)

    async def _execute_step(self, ctx: HandoffContext, step: dict) -> None:
        """
        Voert één step uit. Koppelt aan bestaande agent-aanroep logica.
        Hergebruikt _run_step_agent_with_timeout uit job_pipeline (geen job_id/pool in signature).
        """
        step_id = step.get("step_id")
        step_name = step.get("step_name", "")
        agent_role = step.get("agent_role", "") or (step.get("agent_id") or "").replace("agent:", "")

        if ctx.is_over_budget():
            raise BudgetExceededError(ctx.job_id)
        if ctx.budget_warning():
            logger.warning("Job %s: token budget >80%% bij start van '%s'", ctx.job_id, step_name)

        started_at = datetime.now(timezone.utc)
        if step_id:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "UPDATE job_steps SET status = 'running', started_at = $1 WHERE id = $2",
                    started_at,
                    step_id,
                )

        from app.services.job_pipeline import (
            _coerce_context,
            _run_step_agent_with_timeout,
        )
        from app.services.token_guard import TokenGuard

        token_guard = TokenGuard(db_pool=self._pool)
        check = await token_guard.check_before_call(ctx.job_id, estimated_tokens=2000)
        if not check.get("allowed", True):
            raise BudgetExceededError(ctx.job_id)

        async with self._pool.acquire() as conn:
            job_row = await conn.fetchrow(
                "SELECT job_post, context, status FROM jobs WHERE id = $1",
                ctx.job_id,
            )
        job_context = _coerce_context(job_row.get("context") if job_row else None)
        job_post = (job_row.get("job_post") or "") if job_row else ""
        agent_context: Dict[str, Any] = {
            "brief": ctx.strategic_brief,
            "objective": job_context.get("objective", job_post),
            "job_post": job_post,
            "platform": ctx.platform,
            "_knowledge_block": job_context.get("_knowledge_block", ""),
        }
        previous_content = "\n\n".join(
            f"[{name}]\n{out}"
            for name, out in ctx.step_outputs.items()
            if out
        )
        if previous_content:
            agent_context["previous_content"] = previous_content

        output_to_store: Dict[str, Any]
        try:
            output_dict, tokens_used = await _run_step_agent_with_timeout(
                agent_role=agent_role,
                step_name=step_name,
                context=agent_context,
                previous_content=previous_content or None,
            )
            output_to_store = output_dict
            output_text = (
                output_dict.get("content")
                or output_dict.get("review")
                or (json.dumps(output_dict, default=_json_default) if output_dict else "")
            )
            if not isinstance(output_text, str):
                output_text = str(output_text)
            feedback = output_dict.get("feedback", "")
            error = output_dict.get("error")
        except Exception as e:
            logger.error("Step '%s' fout: %s", step_name, e, exc_info=True)
            output_text, tokens_used, feedback, error = "", 0, "", str(e)
            output_to_store = {"status": "failed", "error": str(e), "agent_role": agent_role}

        ctx.register_tokens(tokens_used)
        try:
            await token_guard.register_usage(ctx.job_id, tokens_used, step_id)
        except Exception as e:
            logger.debug("TokenGuard register_usage skip (step_id may be missing): %s", e)

        ctx.step_outputs[step_name] = output_text
        if feedback:
            ctx.step_feedback[step_name] = feedback

        completed_at = datetime.now(timezone.utc)
        timing_ms = int((completed_at - started_at).total_seconds() * 1000)
        final_status = "failed" if error else "completed"
        if step_id:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE job_steps
                    SET status = $1, completed_at = $2, output = $3::jsonb, tokens_used = $4, timing_ms = $5, progress_pct = 100
                    WHERE id = $6
                    """,
                    final_status,
                    completed_at,
                    json.dumps(output_to_store, default=_json_default),
                    tokens_used,
                    timing_ms,
                    step_id,
                )

    async def _update_job_status(
        self, job_id: str, status: str, ctx: HandoffContext
    ) -> None:
        """Update jobs.status. Token usage wordt bijgehouden door TokenGuard.register_usage."""
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status = $1, updated_at = now() WHERE id = $2",
                status,
                job_id,
            )
        logger.info("Job %s → %s", job_id, status)

    async def _update_job_context(self, job_id: str, updates: Dict[str, Any]) -> None:
        """
        Mergt updates in het bestaande jobs.context JSONB veld.
        Hergebruikt geen job_pipeline helper (die neemt conn); hier gebruiken we pool + JSONB merge.
        """
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET context = COALESCE(context, '{}'::jsonb) || $1::jsonb,
                    updated_at = now()
                WHERE id = $2
                """,
                json.dumps(updates, default=_json_default),
                job_id,
            )
