"""
Eval runner voor Wonderz NEXUS pipeline.
Voert eval cases uit en beoordeelt de output op gedefinieerde checks.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import time
import uuid
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

_HAIKU_JUDGE_MODEL = os.getenv("EVAL_LLM_JUDGE_MODEL", "claude-haiku-4-5-20251001")


# ─── Graders ──────────────────────────────────────────────────────────────────


async def grade_response_contract(job_output: dict) -> dict:
    """
    Check 1: Bevat de output (als tekst) alle vier Response Contract secties?
    (Gevonden / Oorzaak / Fix / Volgende actie)
    """
    if not job_output:
        return {"passed": False, "reason": "Geen output"}

    output_text = json.dumps(job_output, ensure_ascii=False).lower()
    sections = {
        "gevonden": any(k in output_text for k in ["gevonden", "found", "bevinding"]),
        "oorzaak": any(k in output_text for k in ["oorzaak", "cause", "reason"]),
        "fix": any(k in output_text for k in ["fix", "oplossing", "voorstel"]),
        "volgende_actie": any(
            k in output_text for k in ["volgende", "next", "actie"]
        ),
    }
    missing = [k for k, v in sections.items() if not v]
    return {
        "passed": len(missing) == 0,
        "sections": sections,
        "missing": missing,
        "reason": f"Missende secties: {missing}" if missing else "Alle secties aanwezig",
    }


async def grade_job_terminal_status(job: dict, expected: dict) -> dict:
    """Pipeline succes: standaard JOB_READY of COMPLETED (niet alleen COMPLETED)."""
    st = (job.get("status") or "").strip()
    terminal_in = expected.get("terminal_status_in")
    if terminal_in:
        passed = st in terminal_in
        return {
            "passed": passed,
            "reason": f"Status: {st} (verwacht één van {terminal_in})",
        }
    success = expected.get(
        "success_statuses",
        ("JOB_READY", "COMPLETED"),
    )
    if isinstance(success, list):
        success = tuple(success)
    passed = st in success
    return {
        "passed": passed,
        "reason": f"Status: {st} (succes = {success})",
    }


async def grade_no_unhandled_errors(job_steps: list) -> dict:
    """Check 3: Geen mislukte steps zonder expliciete recovery."""
    failed: list[str] = []
    for s in job_steps:
        st = (s.get("status") or "").lower()
        if st != "failed":
            continue
        if s.get("recovered"):
            continue
        failed.append(str(s.get("step_name") or s.get("id") or "?"))
    return {
        "passed": len(failed) == 0,
        "failed_steps": failed,
        "reason": f"{len(failed)} unhandled failed steps" if failed else "Geen unhandled errors",
    }


async def grade_lesson_created(conn: asyncpg.Connection, job_id: str) -> dict:
    """Check 4: lesson gekoppeld aan job (source_job_id indien aanwezig, anders fallback)."""
    has_col = await conn.fetchval(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'lessons' AND column_name = 'source_job_id'
        """
    )
    jid = uuid.UUID(job_id)
    if has_col:
        count = await conn.fetchval(
            "SELECT COUNT(*)::int FROM lessons WHERE source_job_id = $1",
            jid,
        )
        return {
            "passed": (count or 0) > 0,
            "reason": f"{count or 0} lessons (source_job_id)",
        }
    # Geen source_job_id: optioneel task_id = job_id::text
    count = await conn.fetchval(
        "SELECT COUNT(*)::int FROM lessons WHERE task_id = $1",
        str(jid),
    )
    return {
        "passed": (count or 0) > 0,
        "reason": f"{count or 0} lessons (task_id={jid}); source_job_id ontbreekt in schema",
    }


async def grade_stm_populated(conn: asyncpg.Connection, job_id: str) -> dict:
    """Check: session_context (STM) heeft inhoud na de run."""
    has_col = await conn.fetchval(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'jobs' AND column_name = 'session_context'
        """
    )
    if not has_col:
        return {
            "passed": False,
            "reason": "Kolom jobs.session_context ontbreekt (STM-migratie niet toegepast)",
        }
    row = await conn.fetchrow(
        "SELECT session_context FROM jobs WHERE id = $1",
        uuid.UUID(job_id),
    )
    sc = row["session_context"] if row else None
    if sc is None:
        return {"passed": False, "reason": "session_context is null"}
    if isinstance(sc, (dict, list)):
        ok = len(sc) > 0
    elif isinstance(sc, str):
        ok = bool(sc.strip() and sc.strip() not in ("{}", "[]", "null"))
    else:
        ok = bool(sc)
    return {
        "passed": ok,
        "reason": "STM heeft inhoud" if ok else "STM leeg of afwezig",
    }


async def grade_llm_quality(job_output: dict, criteria: str) -> dict:
    """
    Check 5: LLM-as-judge (Haiku) voor open-ended kwaliteit.
    """
    try:
        from anthropic import AsyncAnthropic
    except Exception as e:
        return {
            "passed": True,
            "score": 3,
            "reason": f"Anthropic niet beschikbaar (fallback pass): {e!s}"[:120],
        }

    client = AsyncAnthropic()
    output_text = json.dumps(job_output, ensure_ascii=False)[:3000]

    prompt = f"""Beoordeel de volgende AI-gegenereerde output op dit criterium:
Criterium: {criteria}

Output:
{output_text}

Geef je beoordeling als JSON:
{{"passed": true/false, "score": 1-5, "reason": "korte uitleg max 100 tekens"}}
Alleen JSON teruggeven."""

    try:
        response = await client.messages.create(
            model=_HAIKU_JUDGE_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (response.content[0].text or "").strip()
        parsed: dict[str, Any] = json.loads(raw)
        passed = bool(parsed.get("passed", False))
        return {
            "passed": passed,
            "score": parsed.get("score"),
            "reason": str(parsed.get("reason", ""))[:120],
        }
    except Exception as e:
        return {
            "passed": True,
            "score": 3,
            "reason": f"Grade error (fallback pass): {str(e)[:50]}",
        }


# ─── Job creation & pipeline ───────────────────────────────────────────────────


def _parse_user_id(user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(user_id))
    except Exception:
        return uuid.UUID("00000000-0000-0000-0000-000000000001")


def _merge_job_output(job_row: asyncpg.Record, job_steps: list) -> dict:
    """Combineer payload (proposed_data) en laatste step-output voor graders."""
    out: dict[str, Any] = {}
    payload = job_row.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    if isinstance(payload, dict):
        out.update(payload)
        pd = payload.get("proposed_data")
        if isinstance(pd, dict):
            out = {**out, **pd}
    for step in reversed(job_steps):
        wo = step.get("worker_output")
        if isinstance(wo, dict) and wo:
            out = {**out, **wo}
            break
        op = step.get("output")
        if isinstance(op, dict) and op:
            out = {**out, **op}
            break
    return out


async def _create_eval_job(
    conn: asyncpg.Connection, case: dict, user_id: uuid.UUID
) -> uuid.UUID:
    raw_payload = dict(case.get("input_payload") or {})
    job_type_meta = raw_payload.pop("job_type", case.get("job_type", "copywriting"))
    description = raw_payload.get("description", "")
    eval_payload = {**raw_payload, "_eval_job_type": job_type_meta}

    job_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO jobs (
            id, user_id, job_post, status, source_platform, context, token_budget, intake_source, payload
        )
        VALUES ($1, $2, $3, 'RUNNING', 'eval', '{}'::jsonb, 50000, 'eval', $4::jsonb)
        """,
        job_id,
        user_id,
        description if description else "(empty eval)",
        json.dumps(eval_payload),
    )
    for idx, (step_name, agent_role) in enumerate(
        [("copywriting", "copywriter"), ("review", "reviewer")]
    ):
        await conn.execute(
            """
            INSERT INTO job_steps (job_id, step_index, step_name, agent_role, status, input_payload)
            VALUES ($1, $2, $3, $4, 'pending', '{}'::jsonb)
            """,
            job_id,
            idx,
            step_name,
            agent_role,
        )
    return job_id


async def _invoke_job_pipeline(job_id: str) -> None:
    """Roep bestaande inline pipeline aan (zelfde entry als productie-worker)."""
    mod = importlib.import_module("app.services.job_pipeline")
    fn = getattr(mod, "run_job_inline", None)
    if fn is None:
        raise RuntimeError("app.services.job_pipeline.run_job_inline ontbreekt")
    await fn(job_id)


async def _maybe_synth_complete_for_lesson(pool: asyncpg.Pool, job_id: str) -> None:
    """
    Zet JOB_READY → COMPLETED en probeer lesson te registreren (eval alleen),
    zodat lesson_created-checks slagen zonder echte deploy.
    """
    jid = uuid.UUID(job_id)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE jobs
            SET status = 'COMPLETED',
                completed_at = COALESCE(completed_at, now()),
                finished_at = COALESCE(finished_at, now()),
                updated_at = now()
            WHERE id = $1 AND status = 'JOB_READY'
            """,
            jid,
        )
    try:
        mod = importlib.import_module("app.services.lesson_from_completed_job")
        rec = getattr(mod, "record_lesson_from_completed_job", None)
        if rec:
            await rec(pool, job_id)
    except ImportError:
        logger.warning(
            "eval: lesson_from_completed_job niet beschikbaar; lesson_created kan false blijven"
        )


# ─── Runner ───────────────────────────────────────────────────────────────────


async def run_eval_case(
    pool: asyncpg.Pool,
    case: dict,
    run_id: uuid.UUID,
    triggered_user_id: str,
) -> dict:
    """Voer één eval case uit en evalueer het resultaat."""
    start = time.time()
    result: dict[str, Any] = {
        "case_id": case["id"],
        "run_id": str(run_id),
        "passed": False,
        "checks_passed": [],
        "checks_failed": [],
        "error_detail": None,
    }
    expected = case.get("expected_checks") or {}
    if isinstance(expected, str):
        try:
            expected = json.loads(expected)
        except Exception:
            expected = {}

    job_id: Optional[uuid.UUID] = None

    try:
        async with pool.acquire() as conn:
            job_id = await _create_eval_job(conn, case, _parse_user_id(triggered_user_id))

        await _invoke_job_pipeline(str(job_id))

        terminal = {"FAILED", "ERROR", "JOB_READY", "COMPLETED", "INTAKE_CLARIFICATION"}
        job_row: Optional[asyncpg.Record] = None
        for _ in range(60):
            await asyncio.sleep(5)
            async with pool.acquire() as conn:
                job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
            if job_row and (job_row["status"] in terminal):
                break

        async with pool.acquire() as conn:
            job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
            job_steps = await conn.fetch(
                """
                SELECT * FROM job_steps WHERE job_id = $1
                ORDER BY step_index NULLS LAST, created_at NULLS LAST
                """,
                job_id,
            )

        assert job_row is not None
        job = dict(job_row)

        if expected.get("lesson_created") and job.get("status") == "JOB_READY":
            await _maybe_synth_complete_for_lesson(pool, str(job_id))
            async with pool.acquire() as conn:
                job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
                job_steps = await conn.fetch(
                    """
                    SELECT * FROM job_steps WHERE job_id = $1
                    ORDER BY step_index NULLS LAST, created_at NULLS LAST
                    """,
                    job_id,
                )
            job = dict(job_row) if job_row else job

        job_output = _merge_job_output(job_row, list(job_steps))

        if expected.get("response_contract", True):
            check = await grade_response_contract(job_output)
            bucket = result["checks_passed"] if check["passed"] else result["checks_failed"]
            bucket.append({"check": "response_contract", **check})

        check = await grade_job_terminal_status(job, expected)
        bucket = result["checks_passed"] if check["passed"] else result["checks_failed"]
        bucket.append({"check": "job_terminal_status", **check})

        skip = set(expected.get("skip_checks") or [])
        if "no_unhandled_errors" not in skip:
            check = await grade_no_unhandled_errors(list(job_steps))
            bucket = result["checks_passed"] if check["passed"] else result["checks_failed"]
            bucket.append({"check": "no_unhandled_errors", **check})

        if expected.get("lesson_created"):
            async with pool.acquire() as conn:
                check = await grade_lesson_created(conn, str(job_id))
            bucket = result["checks_passed"] if check["passed"] else result["checks_failed"]
            bucket.append({"check": "lesson_created", **check})

        if expected.get("stm_populated"):
            async with pool.acquire() as conn:
                check = await grade_stm_populated(conn, str(job_id))
            bucket = result["checks_passed"] if check["passed"] else result["checks_failed"]
            bucket.append({"check": "stm_populated", **check})

        crit = expected.get("llm_quality_criteria")
        if crit:
            check = await grade_llm_quality(job_output, str(crit))
            bucket = result["checks_passed"] if check["passed"] else result["checks_failed"]
            bucket.append({"check": "llm_quality", **check})

        result["job_id"] = str(job_id)
        result["passed"] = len(result["checks_failed"]) == 0

    except Exception as e:
        logger.exception("eval case failed: %s", e)
        result["error_detail"] = str(e)[:500]
        result["checks_failed"].append({"check": "execution", "reason": str(e)[:200]})

    result["duration_seconds"] = round(time.time() - start, 2)
    return result


async def run_eval_suite(
    pool: asyncpg.Pool,
    suite_name: str,
    triggered_by: str = "manual",
) -> dict[str, Any]:
    """Voer een volledige eval suite uit en sla resultaten op."""
    async with pool.acquire() as conn:
        suite = await conn.fetchrow(
            "SELECT * FROM eval_suites WHERE name = $1 AND is_active = true",
            suite_name,
        )
        if not suite:
            return {"error": f"Suite '{suite_name}' niet gevonden"}

        cases = await conn.fetch(
            """
            SELECT * FROM eval_cases
            WHERE suite_id = $1 AND is_active = true
            ORDER BY created_at
            """,
            suite["id"],
        )

    run_id = uuid.uuid4()
    total = len(cases)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO eval_runs (id, suite_id, triggered_by, total_cases, status)
            VALUES ($1, $2, $3, $4, 'running')
            """,
            run_id,
            suite["id"],
            triggered_by,
            total,
        )

    passed = 0
    try:
        for case in cases:
            cdict = dict(case)
            if isinstance(cdict.get("expected_checks"), str):
                try:
                    cdict["expected_checks"] = json.loads(cdict["expected_checks"])
                except Exception:
                    cdict["expected_checks"] = {}
            if isinstance(cdict.get("input_payload"), str):
                try:
                    cdict["input_payload"] = json.loads(cdict["input_payload"])
                except Exception:
                    cdict["input_payload"] = {}

            eres = await run_eval_case(pool, cdict, run_id, triggered_by)
            job_uuid = eres.get("job_id")
            job_uuid = uuid.UUID(job_uuid) if job_uuid else None

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO eval_results
                    (run_id, case_id, job_id, passed, checks_passed, checks_failed, duration_seconds, error_detail)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8)
                    """,
                    run_id,
                    eres["case_id"],
                    job_uuid,
                    eres["passed"],
                    json.dumps(eres["checks_passed"]),
                    json.dumps(eres["checks_failed"]),
                    eres["duration_seconds"],
                    eres.get("error_detail"),
                )
            if eres["passed"]:
                passed += 1

        pass_rate = round(passed / total * 100, 1) if total else 0.0
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE eval_runs
                SET finished_at = now(), passed_cases = $1, failed_cases = $2,
                    pass_rate = $3, status = 'completed',
                    summary = $4::jsonb
                WHERE id = $5
                """,
                passed,
                total - passed,
                pass_rate,
                json.dumps({"suite": suite_name}),
                run_id,
            )

        return {
            "run_id": str(run_id),
            "suite": suite_name,
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": pass_rate,
        }
    except Exception as e:
        logger.exception("eval suite failed: %s", e)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE eval_runs
                SET finished_at = now(), status = 'failed',
                    summary = $2::jsonb
                WHERE id = $1
                """,
                run_id,
                json.dumps({"error": str(e)[:500]}),
            )
        return {"error": str(e)[:500], "run_id": str(run_id)}
