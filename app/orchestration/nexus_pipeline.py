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
from app.websocket.manager import manager

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


def _missing_roles_for_payload(missing: list) -> list[str]:
    """Leesbare regels voor payload.missing_roles (frontend)."""
    out: list[str] = []
    for m in missing:
        if not isinstance(m, dict):
            continue
        slot = m.get("slot", "") or ""
        reason = m.get("reason", "") or ""
        if slot and reason:
            out.append(f"{slot}: {reason}")
        elif reason:
            out.append(str(reason))
        elif slot:
            out.append(str(slot))
    return out


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
            if await self._ceo_preset_gate(ctx, job_post):
                return ctx
            await self.phase_2_planning(ctx)
            await self.phase_3_execution(ctx)
            await self.phase_4_qa_loop(ctx)
            await self.phase_5_ceo_review(ctx)
            await self.phase_6_approval_gate(ctx)
            await self.phase_7_deploy(ctx)
        except BudgetExceededError:
            ctx.error = "token_budget_exceeded"
            try:
                from app.services.system_events_service import get_system_events, SystemEventsService
                svc = get_system_events()
                if svc:
                    await svc.log_event(
                        event_type=SystemEventsService.TOKEN_BUDGET_EXCEEDED,
                        severity=SystemEventsService.CRITICAL,
                        job_id=ctx.job_id,
                        agent_id="agent:ceo",
                        message=f"Token budget overschreden voor job {ctx.job_id}: {getattr(ctx, 'token_used_total', 0)}/{ctx.token_budget}",
                        details={"token_count": getattr(ctx, "token_used_total", 0), "budget": ctx.token_budget},
                    )
            except Exception as _log:
                logger.debug("System event log (token budget) skipped: %s", _log)
            await self._update_job_status(ctx.job_id, "FAILED", ctx)
        except Exception as e:
            ctx.error = str(e)
            logger.error("Pipeline fout job %s: %s", job_id, e, exc_info=True)
            try:
                import traceback
                from app.services.system_events_service import get_system_events, SystemEventsService
                svc = get_system_events()
                if svc:
                    await svc.log_event(
                        event_type=SystemEventsService.ORCHESTRATOR_ERROR,
                        severity=SystemEventsService.ERROR,
                        job_id=job_id,
                        agent_id="agent:ceo",
                        message=f"CEO kon geen plan genereren voor job {job_id}",
                        details={"error": str(e), "traceback": traceback.format_exc()},
                    )
            except Exception as _log:
                logger.debug("System event log (orchestrator error) skipped: %s", _log)
            await self._update_job_status(ctx.job_id, "FAILED", ctx)
        return ctx

    async def phase_1_intake(self, ctx: HandoffContext, job_post: str) -> None:
        """Bouw StrategicBrief uit job_post. Status blijft RUNNING (we komen uit approve_plan)."""
        from app.services.job_pipeline import _coerce_context
        from app.orchestration.intake_engine import detect_language, normalize_language_label

        language: Optional[str] = None
        brief_inner: Dict[str, Any] = {}
        if self._pool:
            async with self._pool.acquire() as conn:
                job_row = await conn.fetchrow(
                    "SELECT payload, context FROM jobs WHERE id = $1",
                    ctx.job_id,
                )
            raw = (job_row.get("payload") or job_row.get("context")) if job_row else None
            jc = _coerce_context(raw)
            stored = jc.get("brief")
            if isinstance(stored, dict):
                inner = stored.get("context")
                if isinstance(inner, dict):
                    brief_inner = dict(inner)
                lang_cand = stored.get("language") or brief_inner.get("language")
                if lang_cand:
                    language = normalize_language_label(str(lang_cand), job_post or "")
        if not language:
            language = detect_language(job_post or "")

        ctx.strategic_brief = {
            "objective": job_post,
            "platform": ctx.platform,
            "language": language,
            "context": brief_inner,
        }

    async def _ceo_preset_gate(self, ctx: HandoffContext, job_post: str) -> bool:
        """
        Na jobbeschrijving: preset detecteren + resourcecheck vóór execution plan laden.
        Returns True als job op BLOCKED gezet is en de pipeline moet stoppen.
        """
        from app.orchestration.ceo_intent import (
            build_execution_plan,
            check_resources,
            compute_deviation_slots,
            detect_job_type,
            register_preset_bookings,
        )
        from app.services.job_pipeline import _insert_plan_steps
        from app.services.skill_matcher import (
            UNKNOWN_PRESET_AND_SKILL_MESSAGE,
            match_skill,
            persist_matched_skill,
        )

        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            preset_id = await detect_job_type(conn, job_post or "")
            if not preset_id:
                matched = await match_skill(conn, job_post or "")
                if matched:
                    await persist_matched_skill(conn, ctx.job_id, matched)
                    logger.info(
                        "Job %s: geen preset, matched_skill=%s",
                        ctx.job_id,
                        matched.get("skill_id"),
                    )
                    return False
                await self._block_job(
                    ctx,
                    UNKNOWN_PRESET_AND_SKILL_MESSAGE,
                    missing_roles=[],
                )
                return True
            report = await check_resources(conn, preset_id)
            if not report.get("ready"):
                missing_roles = _missing_roles_for_payload(report.get("missing") or [])
                await self._block_job(
                    ctx,
                    str(report.get("message") or "Resources niet beschikbaar."),
                    missing_roles=missing_roles,
                )
                return True
            n = await conn.fetchval(
                "SELECT COUNT(*)::int FROM job_steps WHERE job_id = $1",
                ctx.job_id,
            )
            plan = await build_execution_plan(conn, ctx.job_id, preset_id, report)
            if n == 0:
                await _insert_plan_steps(conn, ctx.job_id, plan)
            else:
                plan_blob = json.loads(plan.model_dump_json())
                await conn.execute(
                    """
                    UPDATE jobs
                    SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                        updated_at = now()
                    WHERE id = $2
                    """,
                    json.dumps(
                        {"preset_id": str(preset_id), "preset_execution_plan": plan_blob},
                        default=_json_default,
                    ),
                    ctx.job_id,
                )
            dev_slots = await compute_deviation_slots(conn, ctx.job_id)
            await register_preset_bookings(
                conn,
                ctx.job_id,
                preset_id,
                report.get("covered") or [],
                deviation_slots=dev_slots,
            )
        return False

    async def _block_job(
        self,
        ctx: HandoffContext,
        message: str,
        missing_roles: Optional[list] = None,
    ) -> None:
        """Zet job op BLOCKED met reden en ontbrekende rollen in payload."""
        ctx.error = message
        if not self._pool:
            return
        roles = missing_roles if missing_roles is not None else []
        block_payload: Dict[str, Any] = {
            "block_reason": message,
            "ceo_preset_blocked": True,
            "missing_roles": roles,
        }
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = $1, updated_at = now(),
                    payload = COALESCE(payload, '{}'::jsonb) || $2::jsonb
                WHERE id = $3
                """,
                "BLOCKED",
                block_payload,
                ctx.job_id,
            )
            # Zelfde HR-notifier als job_pipeline._block_job (ARQ → nexus zonder job_pipeline gate).
            try:
                from app.services.hr_blocked_job_notifier import (
                    notify_blocked_job_improvements,
                )

                await notify_blocked_job_improvements(
                    conn=conn,
                    job_id=str(ctx.job_id),
                    block_reason=message,
                    missing_roles=roles,
                )
            except Exception:
                logger.exception(
                    "[nexus_pipeline] HR blocked job notifier failed job=%s",
                    ctx.job_id,
                )
        await manager.broadcast_job_update(str(ctx.job_id), {
            "job_id": str(ctx.job_id),
            "status": "BLOCKED",
        })
        logger.info("Job %s → BLOCKED: %s", ctx.job_id, message[:200])

    def _merge_depends_on_into_steps(
        self, steps: list, job_context: dict
    ) -> None:
        """Merge depends_on from plan in job context into each step dict (by step_index). In-place."""
        plan = job_context.get("plan") if isinstance(job_context, dict) else None
        plan_steps = plan.get("steps", []) if isinstance(plan, dict) else []
        by_index = {s.get("step_index"): s for s in plan_steps if isinstance(s, dict) and s.get("step_index") is not None}
        for step in steps:
            idx = step.get("step_index")
            if idx is not None and idx in by_index:
                dep = by_index[idx].get("depends_on")
                if isinstance(dep, list):
                    step["depends_on"] = dep
            if "depends_on" not in step:
                step["depends_on"] = []

    async def phase_2_planning(self, ctx: HandoffContext) -> None:
        """
        Laadt execution_plan uit job_steps tabel.
        Merge depends_on uit job context (plan.steps) in ctx.execution_plan — kritiek voor phase_3.
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

        # Merge depends_on from job context (plan) so phase_3 can decide waves
        async with self._pool.acquire() as conn:
            job_row = await conn.fetchrow(
                "SELECT payload, context FROM jobs WHERE id = $1",
                ctx.job_id,
            )
        raw = (job_row.get("payload") or job_row.get("context")) if job_row else None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                raw = {}
        job_context = raw if isinstance(raw, dict) else {}
        self._merge_depends_on_into_steps(ctx.execution_plan, job_context)

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
                "depends_on": [],
            })
        # Status blijft RUNNING (gezet door approve_plan); phase_3 houdt RUNNING.

    def _is_parallel_ready(self, steps: list) -> bool:
        """False if any step missing depends_on or circular deps → sequential fallback."""
        if not steps:
            return False
        if not all("depends_on" in s for s in steps):
            return False
        for step in steps:
            for dep in step.get("depends_on", []):
                if dep >= step.get("step_index", 0):
                    return False
        return True

    def _get_next_wave(self, steps: list) -> list:
        """Next group of steps that can run in parallel (deps completed, no duplicate agent_role in wave)."""
        completed_indices = {s["step_index"] for s in steps if s.get("status") == "completed"}
        running_roles = {s.get("agent_role") for s in steps if s.get("status") == "running"}
        wave = []
        for step in steps:
            if step.get("status") != "pending":
                continue
            deps = set(step.get("depends_on", []))
            if not deps.issubset(completed_indices):
                continue
            if step.get("agent_role") in running_roles:
                continue
            wave.append(step)
            running_roles.add(step.get("agent_role"))
        return wave

    async def _load_steps(self, job_id: str) -> list:
        """Load job_steps from DB and merge depends_on from job context (plan). Same merge as phase_2."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id AS step_id, step_index, step_name, agent_role, agent_id, input_payload, status, error_log
                FROM job_steps WHERE job_id = $1 ORDER BY step_index ASC
                """,
                job_id,
            )
            job_row = await conn.fetchrow(
                "SELECT payload, context FROM jobs WHERE id = $1",
                job_id,
            )
        steps = []
        for r in rows:
            payload = r.get("input_payload")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload) if payload else {}
                except json.JSONDecodeError:
                    payload = {}
            elif not isinstance(payload, dict):
                payload = {}
            steps.append({
                "step_id": str(r["step_id"]) if r.get("step_id") else None,
                "step_index": r.get("step_index", 0),
                "step_name": r.get("step_name") or f"step_{r.get('step_index', 0)}",
                "agent_role": r.get("agent_role") or "",
                "agent_id": r.get("agent_id"),
                "input_payload": payload,
                "status": r.get("status", "pending"),
                "error_log": r.get("error_log"),
            })
        raw = (job_row.get("payload") or job_row.get("context")) if job_row else None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                raw = {}
        self._merge_depends_on_into_steps(steps, raw if isinstance(raw, dict) else {})
        return steps

    async def _mark_step_failed(self, job_id: str, step_id: str, error: str) -> None:
        """Mark step as failed (WHERE id = step_id, consistent with _execute_step)."""
        if not step_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE job_steps
                SET status = 'failed', error_log = $1, completed_at = now()
                WHERE id = $2
                """,
                error,
                int(step_id),
            )

    async def _handle_pipeline_failure(self, job_id: str, ctx: HandoffContext, error_info: dict) -> None:
        """Set job to FAILED and log."""
        err_msg = error_info.get("error") or str(error_info)
        ctx.error = err_msg
        await self._update_job_status(job_id, "FAILED", ctx)
        logger.warning("Pipeline failure job %s: %s", job_id, err_msg)

    async def _run_pipeline_sequential(self, ctx: HandoffContext) -> None:
        """Original sequential step loop (fallback when parallel not ready)."""
        for step in ctx.execution_plan:
            await self._execute_step(ctx, step)

    async def _run_pipeline(self, ctx: HandoffContext) -> None:
        """Wave-based parallel execution. Reloads steps via _load_steps each iteration (includes depends_on merge)."""
        job_id = ctx.job_id
        max_iterations = len(ctx.execution_plan) + 5
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            steps = await self._load_steps(job_id)
            pending = [s for s in steps if s.get("status") == "pending"]
            failed = [s for s in steps if s.get("status") == "failed"]
            if failed:
                await self._handle_pipeline_failure(
                    job_id, ctx, {"step_name": failed[0].get("step_name"), "error": failed[0].get("error_log") or "failed"}
                )
                return
            if not pending:
                return
            wave = self._get_next_wave(steps)
            if not wave:
                await self._handle_pipeline_failure(
                    job_id, ctx, {"step_name": "pipeline", "error": "Geen uitvoerbare stappen. Mogelijke deadlock."}
                )
                return
            if len(wave) == 1:
                await self._execute_step(ctx, wave[0])
            else:
                results = await asyncio.gather(
                    *[self._execute_step(ctx, step) for step in wave],
                    return_exceptions=True,
                )
                for step, result in zip(wave, results):
                    if isinstance(result, Exception):
                        await self._mark_step_failed(job_id, step.get("step_id") or "", str(result))
                        if self._pool:
                            try:
                                from app.services.agent_performance import record_step_completion

                                aid = step.get("agent_id")
                                if aid:
                                    sid = aid.strip() if isinstance(aid, str) else str(aid)
                                    if sid:
                                        await record_step_completion(self._pool, sid, success=False)
                            except Exception as perf_e:
                                logger.warning(
                                    "Performance tracking (parallel failure) skipped: %s",
                                    perf_e,
                                    exc_info=True,
                                )
                        await self._handle_pipeline_failure(job_id, ctx, {"error": str(result)})
                        return
        await self._handle_pipeline_failure(
            job_id, ctx, {"step_name": "pipeline", "error": f"Pipeline niet afgerond na {max_iterations} iteraties."}
        )

    async def phase_3_execution(self, ctx: HandoffContext) -> None:
        """Voer steps uit: parallel (wave) als plan depends_on heeft, anders sequentieel."""
        await self._update_job_status(ctx.job_id, "RUNNING", ctx)
        logger.info(
            "Pipeline mode — steps depends_on: %s",
            [{"idx": s.get("step_index"), "deps": s.get("depends_on")} for s in ctx.execution_plan],
        )
        logger.info(
            "is_parallel_ready: %s",
            self._is_parallel_ready(ctx.execution_plan),
        )
        if self._is_parallel_ready(ctx.execution_plan):
            await self._run_pipeline(ctx)
        else:
            await self._run_pipeline_sequential(ctx)

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
                "SELECT job_post, payload FROM jobs WHERE id = $1",
                ctx.job_id,
            )
        job_context = _coerce_context(job_row.get("payload") if job_row else None)
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
                job_id=str(ctx.job_id),
                job_step_id=None,
                agent_id="ceo_review",
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
        Schrijft die als final_content naar jobs.payload.
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
        Voert één step uit. Max 3 pogingen bij technisch falen (timeout, API error).
        QA-loop retries in phase_4 blijven voor output-kwaliteit; dit is alleen technisch.
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
                    int(step_id) if step_id is not None else None,
                )

        from app.services.job_pipeline import (
            _coerce_context,
            _parse_seo_handoff_from_llm_text,
            _run_step_agent_with_timeout,
        )
        from app.services.token_guard import TokenGuard

        token_guard = TokenGuard(db_pool=self._pool)
        check = await token_guard.check_before_call(ctx.job_id, estimated_tokens=2000)
        if not check.get("allowed", True):
            raise BudgetExceededError(ctx.job_id)

        async with self._pool.acquire() as conn:
            job_row = await conn.fetchrow(
                "SELECT job_post, payload, status FROM jobs WHERE id = $1",
                ctx.job_id,
            )
        job_context = _coerce_context(job_row.get("payload") if job_row else None)
        job_post = (job_row.get("job_post") or "") if job_row else ""
        # SEO/copywriter system prompts are built in app.services.job_pipeline._run_step_agent
        # using context["brief"] (strategic_brief) and _brief_ctx for language
        # (strategic_brief.context.language or strategic_brief.language).
        agent_context: Dict[str, Any] = {
            "brief": ctx.strategic_brief,
            "objective": job_context.get("objective", job_post),
            "job_post": job_post,
            "platform": ctx.platform,
            "_knowledge_block": job_context.get("_knowledge_block", ""),
        }
        if ctx.seo_keywords or (ctx.focus_keyword or "").strip():
            agent_context["seo_keywords"] = list(ctx.seo_keywords)
            agent_context["focus_keyword"] = ctx.focus_keyword
            agent_context["keyword_intent"] = ctx.keyword_intent
        previous_content = "\n\n".join(
            f"[{name}]\n{out}"
            for name, out in ctx.step_outputs.items()
            if out
        )
        if previous_content:
            agent_context["previous_content"] = previous_content

        output_to_store: Dict[str, Any]
        tokens_used = 0
        output_text = ""
        feedback = ""
        error: Optional[str] = None
        retries_done = 0

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                aid = step.get("agent_id")
                output_dict, tokens_used = await _run_step_agent_with_timeout(
                    agent_role=agent_role,
                    step_name=step_name,
                    context=agent_context,
                    previous_content=previous_content or None,
                    job_id=str(ctx.job_id),
                    job_step_id=str(step_id) if step_id else None,
                    agent_id=str(aid) if aid else None,
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
                break
            except Exception as e:
                retries_done = attempt
                error = str(e)
                logger.warning(
                    "Step '%s' attempt %s/%s failed: %s",
                    step_name, attempt, self.MAX_RETRIES, e,
                    exc_info=(attempt == self.MAX_RETRIES),
                )
                if attempt < self.MAX_RETRIES:
                    continue
                output_text, tokens_used = "", 0
                output_to_store = {"status": "failed", "error": error, "agent_role": agent_role}

        ctx.register_tokens(tokens_used)
        try:
            await token_guard.register_usage(ctx.job_id, tokens_used, step_id)
        except Exception as e:
            logger.debug("TokenGuard register_usage skip (step_id may be missing): %s", e)

        ctx.step_outputs[step_name] = output_text
        if feedback:
            ctx.step_feedback[step_name] = feedback

        role_for_handoff = (agent_role or "").strip().lower()
        if not error and role_for_handoff == "seo":
            parsed = _parse_seo_handoff_from_llm_text(output_text)
            ctx.seo_keywords = parsed.get("seo_keywords") or []
            ctx.focus_keyword = parsed.get("focus_keyword") or ""
            ctx.keyword_intent = parsed.get("keyword_intent") or ""

        completed_at = datetime.now(timezone.utc)
        timing_ms = int((completed_at - started_at).total_seconds() * 1000)
        final_status = "failed" if error else "completed"
        error_log_value: Optional[str] = error if final_status == "failed" else None
        if step_id:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE job_steps
                    SET status = $1, completed_at = $2, output = $3::jsonb, tokens_used = $4,
                        timing_ms = $5, progress_pct = 100, error_log = $6, retry_count = $7
                    WHERE id = $8
                    """,
                    final_status,
                    completed_at,
                    json.dumps(output_to_store, default=_json_default),
                    tokens_used,
                    timing_ms,
                    error_log_value,
                    retries_done,
                    int(step_id) if step_id is not None else None,
                )
            if self._pool:
                try:
                    from app.services.agent_performance import record_step_completion

                    aid = step.get("agent_id")
                    if aid:
                        sid = aid.strip() if isinstance(aid, str) else str(aid)
                        if sid:
                            await record_step_completion(
                                self._pool,
                                sid,
                                success=(final_status == "completed"),
                            )
                except Exception as perf_e:
                    logger.warning(
                        "Performance tracking skipped for step %s: %s",
                        step_name,
                        perf_e,
                        exc_info=True,
                    )

    async def _update_job_status(
        self, job_id: str, status: str, ctx: HandoffContext
    ) -> None:
        """
        Update jobs.status and jobs.payload (token_summary, proposed_data at JOB_READY,
        error_reason at FAILED). Set jobs.finished_at when status is COMPLETED.
        Production schema: payload (JSONB), finished_at; no tokens_used/token_budget columns.
        """
        if not self._pool:
            return
        payload_updates: Dict[str, Any] = {
            "token_summary": {
                "used": ctx.token_used_total,
                "budget": ctx.token_budget,
            },
        }
        if status == "JOB_READY":
            final_content = ""
            for step in reversed(ctx.execution_plan):
                step_name = step.get("step_name", "")
                output = ctx.step_outputs.get(step_name, "")
                if output and step_name != "gtm_analysis":
                    final_content = output if isinstance(output, str) else str(output)
                    break
            payload_updates["proposed_data"] = final_content
        if status == "FAILED" and ctx.error:
            payload_updates["error_reason"] = ctx.error

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COALESCE(payload, '{}'::jsonb) AS p FROM jobs WHERE id = $1",
                job_id,
            )
            cur_payload: Dict[str, Any] = {}
            if row and row.get("p") is not None:
                rawp = row["p"]
                if isinstance(rawp, dict):
                    cur_payload = dict(rawp)
                elif isinstance(rawp, str):
                    try:
                        cur_payload = json.loads(rawp) if rawp.strip() else {}
                    except json.JSONDecodeError:
                        cur_payload = {}

            if status == "JOB_READY":
                preset_id = cur_payload.get("preset_id")
                if isinstance(preset_id, dict):
                    preset_id = preset_id.get("preset_id")
                already_counted = cur_payload.get("preset_usage_counted") is True
                if preset_id and not already_counted:
                    await conn.execute(
                        """
                        UPDATE job_type_presets
                        SET usage_count = COALESCE(usage_count, 0) + 1,
                            updated_at = now()
                        WHERE preset_id = $1
                        """,
                        str(preset_id),
                    )
                    payload_updates["preset_usage_counted"] = True

            payload_json = json.dumps(payload_updates, default=_json_default)
            await conn.execute(
                """
                UPDATE jobs
                SET status = $1, updated_at = now(),
                    payload = COALESCE(payload, '{}'::jsonb) || $2::jsonb,
                    finished_at = CASE WHEN $1 = 'COMPLETED' THEN now() ELSE finished_at END
                WHERE id = $3
                """,
                status,
                payload_json,
                job_id,
            )
        await manager.broadcast_job_update(str(job_id), {
            "job_id": str(job_id),
            "status": status,
        })
        logger.info("Job %s → %s", job_id, status)

    async def _update_job_context(self, job_id: str, updates: Dict[str, Any]) -> None:
        """
        Mergt updates in het bestaande jobs.payload JSONB veld (productie: payload, niet context).
        """
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                    updated_at = now()
                WHERE id = $2
                """,
                json.dumps(updates, default=_json_default),
                job_id,
            )
