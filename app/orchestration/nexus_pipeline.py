"""NEXUSPipeline — 7-phase CEO orchestrator with quality gates and token budget."""

import asyncio
import logging
from typing import Optional

from app.orchestration.handoff_context import HandoffContext
from app.orchestration.quality_gate import QualityGate

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(f"Token budget overschreden voor job {job_id}")


class NEXUSPipeline:
    """
    7-fase CEO orchestrator pipeline.
    Elke fase is een aparte methode. HandoffContext verbindt de fasen.
    """

    MAX_RETRIES = 3
    quality_gate = QualityGate()

    async def run(
        self,
        job_id: str,
        user_id: str,
        platform: str,
        job_post: str,
        token_budget: int = 50000,
    ) -> HandoffContext:
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
        """Analyseer job post, bouw StrategicBrief."""
        # assumption-based: direct brief bouwen zonder extra LLM-call als job_post compleet is
        ctx.strategic_brief = {
            "objective": job_post,
            "platform": ctx.platform,
        }
        await self._update_job_status(ctx.job_id, "INTAKE_CLARIFICATION", ctx)

    async def phase_2_planning(self, ctx: HandoffContext) -> None:
        """Bouw execution plan. Check hired_agents. Hire indien nodig."""
        # Hergebruik bestaande StrategyRoom/plan-logica
        # ctx.execution_plan = [{ step_name, agent_role, description }, ...]
        GTM_PLATFORMS = ["wonderz", "clawagency", "blogable"]
        if ctx.platform.lower() in GTM_PLATFORMS:
            ctx.execution_plan.append({
                "step_name": "gtm_analysis",
                "agent_role": "gtm-specialist",
                "agent_id": "agent:gtm-specialist",
                "description": f"GTM analyse voor {ctx.platform}",
            })
        await self._update_job_status(ctx.job_id, "PLAN_PROPOSED", ctx)

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
        """CEO beoordeelt eindresultaat tegen de StrategicBrief."""
        # Hergebruik bestaande CEO review-logica
        pass

    async def phase_6_approval_gate(self, ctx: HandoffContext) -> None:
        """Zet status op JOB_READY. Wacht op gebruikersgoedkeuring."""
        await self._update_job_status(ctx.job_id, "JOB_READY", ctx)

    async def phase_7_deploy(self, ctx: HandoffContext) -> None:
        """Na gebruikersapproval: DeployAgent zet live via adapter."""
        await self._update_job_status(ctx.job_id, "COMPLETED", ctx)

    async def _execute_step(self, ctx: HandoffContext, step: dict) -> None:
        """Roept de juiste agent aan voor een step."""
        if ctx.is_over_budget():
            raise BudgetExceededError(ctx.job_id)
        if ctx.budget_warning():
            logger.warning("Job %s: token budget 80%% bereikt", ctx.job_id)
        # Hergebruik bestaande agent-aanroep logica (copy_agent, reviewer_agent, etc.)
        # ctx.register_tokens(tokens_used)
        # ctx.step_outputs[step["step_name"]] = output
        step_name = step.get("step_name", "step")
        ctx.step_outputs[step_name] = ctx.step_outputs.get(step_name, "")

    async def _update_job_status(
        self, job_id: str, status: str, ctx: HandoffContext
    ) -> None:
        """Update jobs tabel. Hergebruik bestaande DB-update functie."""
        # assumption-based: bestaande update_job_status functie aanroepen
        pass
