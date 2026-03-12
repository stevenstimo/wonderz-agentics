"""
Email Intake Channel §4.4 & §5: Orchestrator from ParsedEmail to job INSERT.
Full flow: duplicate check → INSERT inbound_emails (pending) → sender check → CEO intake
→ INSERT job → INSERT job_steps → UPDATE inbound_emails (accepted).
On error after first INSERT: UPDATE inbound_emails status=error, error_detail=traceback.
"""

import asyncio
import json
import logging
import re
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic

from app.core.config import DEFAULT_MODEL
from app.db import init_db_pool
from app.services.email_parser import ParsedEmail
from app.services.sender_matcher import SenderMatcher
from app.services.job_pipeline import _insert_plan_steps
from models.unified import ExecutionPlan, JobStep, StrategicBrief

logger = logging.getLogger(__name__)

BODY_TRUNCATE_CHARS = 3000


def _json_default(obj: Any) -> Any:
    """For json.dumps (e.g. context)."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

CEO_EMAIL_INTAKE_PROMPT = """
Je bent de CEO van Crew Intelligent. Je hebt een email ontvangen als job aanvraag.
Jouw taak: analyseer de email, beoordeel de volledigheid, en stel een uitvoerbaar plan op.

## EMAIL INHOUD
Onderwerp: {subject}
Body:
{body}

## STAP 1 — VOLLEDIGHEID BEOORDELEN
Beoordeel de email op vier dimensies (0.0 - 1.0):
- doel_score:    Is het duidelijk wat er gedaan moet worden?
- context_score: Is doelgroep, platform of domein duidelijk?
- scope_score:   Is de omvang, lengte of deliverable duidelijk?
- kpi_score:     Is duidelijk wanneer het goed is?

completeness_score = (doel_score * 0.30) + (context_score * 0.25)
                   + (scope_score * 0.25) + (kpi_score * 0.20)

## STAP 2 — PLAN OPSTELLEN
Stel altijd een plan op, ongeacht de completeness_score.
Ontbrekende informatie = assumption-based stap, expliciet gemarkeerd.

Formatteer aannames als:
  [AANNAME] Doelgroep = professionals 25-45 jaar (niet vermeld in email)

## OUTPUT (JSON, geen markdown)
{{
  "completeness_score": 0.0-1.0,
  "score_breakdown": {{
    "doel": 0.0-1.0,
    "context": 0.0-1.0,
    "scope": 0.0-1.0,
    "kpi": 0.0-1.0
  }},
  "plan": {{
    "steps": [
      {{"agent_role": "copywriter", "description": "...", "assumptions": []}}
    ]
  }},
  "review_note": "Optionele notitie voor gebruiker bij lage score"
}}
"""


def _truncate_body(body: str, max_chars: int = BODY_TRUNCATE_CHARS) -> str:
    """Cap body so one long email does not blow token budget."""
    if not body:
        return ""
    return body[:max_chars] if len(body) > max_chars else body


def _parse_ceo_json(response_text: str) -> dict[str, Any]:
    """
    Parse LLM response as JSON. Explicit fallback on JSONDecodeError:
    strip markdown code fences and retry; then return safe default (no crash).
    """
    text = (response_text or "").strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown code block if present
    stripped = text
    for pattern in (
        r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
        r"^```\s*\n?(.*?)\n?```\s*$",
    ):
        match = re.search(pattern, stripped, re.DOTALL | re.IGNORECASE)
        if match:
            stripped = match.group(1).strip()
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
    # Try extract first {...} object
    start = stripped.find("{")
    if start != -1:
        end = stripped.rfind("}") + 1
        if end > start:
            try:
                return json.loads(stripped[start:end])
            except json.JSONDecodeError:
                pass
    logger.warning("CEO email intake: JSON parse failed, using safe default")
    return {
        "completeness_score": 0.0,
        "score_breakdown": {"doel": 0.0, "context": 0.0, "scope": 0.0, "kpi": 0.0},
        "plan": {"steps": []},
        "review_note": "Kon email niet analyseren; geef meer context via de UI.",
    }


async def _get_pool():
    """Same pattern as job_pipeline: init_db_pool, return None if unavailable (no HTTPException in background)."""
    return await init_db_pool()


def _ceo_plan_to_execution_plan(ceo_plan: dict) -> ExecutionPlan:
    """Build ExecutionPlan from CEO JSON for _insert_plan_steps. Brief is minimal for email flow."""
    steps_raw = ceo_plan.get("steps") or []
    steps: list[JobStep] = []
    for i, s in enumerate(steps_raw, 1):
        if not isinstance(s, dict):
            continue
        # assumption-based: CEO steps may omit unified_tool; job_pipeline uses it for execution.
        steps.append(
            JobStep(
                step_index=i,
                agent_role=str(s.get("agent_role") or "copywriter"),
                unified_tool=str(s.get("unified_tool") or "write_content"),
                requires_approval=bool(s.get("requires_approval", False)),
                description=str(s.get("description") or ""),
            )
        )
    brief = StrategicBrief(
        job_post="",
        is_complete=True,
        clarifications=[],
        context={},
        message=None,
    )
    return ExecutionPlan(brief=brief, steps=steps, hired_agents=[], estimated_duration_seconds=0)


class EmailIntakeProcessor:
    """Orchestrator: duplicate check → inbound_emails INSERT → sender → CEO intake → job → job_steps → inbound_emails UPDATE."""

    @classmethod
    async def process(cls, parsed: ParsedEmail) -> None:
        """
        Strict order: duplicate check → INSERT inbound_emails (pending) → sender check
        → CEO intake → INSERT job → INSERT job_steps → UPDATE inbound_emails (accepted).
        If anything throws after the first INSERT: UPDATE inbound_emails status=error, error_detail=traceback.
        """
        pool = await _get_pool()
        if not pool:
            logger.warning("EmailIntakeProcessor: DB pool not available, skipping")
            return

        email_id = f"email:{parsed.message_id}"

        async with pool.acquire() as conn:
            # 1. Duplicate check
            existing = await conn.fetchrow(
                "SELECT email_id FROM inbound_emails WHERE message_id = $1",
                parsed.message_id,
            )
            if existing:
                return

            # 2. INSERT inbound_emails (pending) — always; record stays for audit
            await conn.execute(
                """
                INSERT INTO inbound_emails (
                    email_id, message_id, from_address, from_name, subject,
                    body_raw, body_clean, received_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                email_id,
                parsed.message_id,
                parsed.from_address or "",
                parsed.from_name or "",
                parsed.subject or "",
                parsed.body_raw or "",
                parsed.body_clean or "",
                parsed.received_at,
            )

        try:
            # 3. Sender check (uses own conn via get_db)
            user_id = await SenderMatcher.match(parsed.from_address or "")
            if not user_id:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE inbound_emails SET status = $1 WHERE email_id = $2",
                        "rejected_sender",
                        email_id,
                    )
                logger.info("Email rejected: unknown sender %s", parsed.from_address)
                return

            # 4. CEO intake
            ceo_result = await cls._run_ceo_intake(parsed)

            job_id = str(uuid.uuid4())
            # Context: plan (full CEO output for UI), completeness_score, score_breakdown, review_note
            context = {
                "plan": ceo_result.get("plan") or {},
                "completeness_score": ceo_result.get("completeness_score"),
                "score_breakdown": ceo_result.get("score_breakdown") or {},
                "review_note": ceo_result.get("review_note") or "",
            }

            async with pool.acquire() as conn:
                # 5. INSERT job — real column names: id, job_post, source_platform, context (no job_id/title/manager_plan)
                await conn.execute(
                    """
                    INSERT INTO jobs (
                        id, user_id, job_post, status, source_platform, context,
                        token_budget, intake_source, inbound_email_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
                    """,
                    job_id,
                    user_id,
                    parsed.subject or "Email job",
                    "PLAN_PROPOSED",
                    "web",
                    json.dumps(context, default=_json_default),
                    50000,
                    "email",
                    email_id,
                )

                # 6. INSERT job_steps (reuse job_pipeline._insert_plan_steps)
                plan = _ceo_plan_to_execution_plan(ceo_result.get("plan") or {})
                await _insert_plan_steps(conn, job_id, plan)

                # 7. UPDATE inbound_emails (accepted)
                await conn.execute(
                    """
                    UPDATE inbound_emails
                    SET status = $1, user_id = $2::uuid, job_id = $3::uuid,
                        completeness_score = $4, processed_at = now()
                    WHERE email_id = $5
                    """,
                    "accepted",
                    user_id,
                    job_id,
                    ceo_result.get("completeness_score"),
                    email_id,
                )
            logger.info("Email intake accepted: email_id=%s job_id=%s", email_id, job_id)

        except Exception as e:
            logger.exception("EmailIntakeProcessor failed after inbound_emails INSERT: %s", e)
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE inbound_emails
                        SET status = $1, error_detail = $2
                        WHERE email_id = $3
                        """,
                        "error",
                        traceback.format_exc(),
                        email_id,
                    )
            except Exception as update_err:
                logger.exception("Failed to set inbound_emails error status: %s", update_err)

    @classmethod
    async def _run_ceo_intake(cls, parsed: ParsedEmail) -> dict[str, Any]:
        """
        Call CEO prompt, parse JSON, return completeness_score + score_breakdown + plan + review_note.
        Body is truncated to BODY_TRUNCATE_CHARS before the LLM call.
        """
        body = _truncate_body(parsed.body_clean or "")
        prompt = CEO_EMAIL_INTAKE_PROMPT.format(
            subject=parsed.subject or "",
            body=body,
        )
        client = Anthropic()

        def _sync_create() -> str:
            resp = client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text if resp.content else ""

        response_text = await asyncio.to_thread(_sync_create)
        return _parse_ceo_json(response_text)
