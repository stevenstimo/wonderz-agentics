"""
Inbox Engine: allowed-sender check → direct chat with CEO → plan_ready / in_chat.

Emails NOT in inbox_allowed_senders are completely ignored (no DB write, no response).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db import init_db_pool
from app.services.email_parser import ParsedEmail
from app.orchestration.direct_chat_engine import DirectChatEngine

logger = logging.getLogger(__name__)

BODY_TRUNCATE_CHARS = 3000

# CEO inbox context: injected as extra_system_block so existing send_message call sites stay unchanged.
def _ceo_inbox_system_block(subject: str, from_name: str, from_address: str, body_clean: str) -> str:
    body = (body_clean or "")[:BODY_TRUNCATE_CHARS]
    return f"""Je hebt een email ontvangen als job aanvraag.
Onderwerp: {subject}
Van: {from_name or '—'} ({from_address or '—'})
Inhoud: {body}

Analyseer de email. Beoordeel op:
- doel (wat moet er gedaan worden?)
- context (doelgroep, platform, domein?)
- scope (omvang, deliverable?)
- kpi (wanneer is het goed?)

Scope-discipline (strikt):
- Maak in je plan alleen werk aan voor exact wat de afzender vraagt. Voeg geen extra taken, agents of deliverables toe die niet gevraagd zijn.
- Als de gebruiker expliciet zegt dat iets níet nodig is, ontbreekt of niet gedaan hoeft te worden: laat dat volledig weg uit het plan en uit de steps.

BELANGRIJK — twee modi, geen tussenweg:
1) Voldoende informatie (jouw inschatting: completeness_score >= 0.7):
   - Je MAG kort samenvatten wat je begrijpt, maar je antwoord is ONVOLLEDIG zonder het formele planblok hieronder.
   - Zodra je voldoende info hebt om een concreet, uitvoerbaar plan te maken, MOET je ALTIJD dit exacte formaat gebruiken (openings- en sluitingsregels letterlijk, JSON op één geldige regel tussen de markers):

%%PLAN%%
{{"steps": [{{"agent_role": "...", "description": "..."}}], "completeness_score": 0.85, "assumptions": []}}
%%/PLAN%%

   - Vul "steps" met concrete stappen (agent_role + description). Zet "completeness_score" op je werkelijke score (0.0–1.0), minimaal 0.7 wanneer je het plan uitstuurt. "assumptions" mag leeg [] zijn of kort wat je aanneemt.
   - Geen planblok = de aanvraag blijft hangen in conversatiemodus; dat is foutgedrag wanneer je al genoeg weet.

2) Onvoldoende informatie (completeness_score < 0.7):
   - Stel maximaal 3 gerichte vragen. Geen %%PLAN%% / %%/PLAN%% blok."""


def _extract_plan_block(text: str) -> dict | None:
    """Extract JSON from %%PLAN%% ... %%/PLAN%%. Returns None if not found or invalid."""
    if not text or "%%PLAN%%" not in text or "%%/PLAN%%" not in text:
        return None
    start = text.find("%%PLAN%%") + len("%%PLAN%%")
    end = text.find("%%/PLAN%%", start)
    if end == -1:
        return None
    raw = text[start:end].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _get_pool():
    """Same pattern as email_intake_processor: no HTTPException in background."""
    return await init_db_pool()


class InboxEngine:
    """
    Process incoming email only when sender is in inbox_allowed_senders.
    Otherwise: no processing, no storage, no response (sender must not know the system exists).
    """

    @classmethod
    async def try_convert_on_chat_user_message(
        cls,
        pool: Any,
        chat_id: str,
        user_id: str,
        user_message: str,
    ) -> dict | None:
        """
        If the user approves a plan_ready inbox thread in chat, create the job and persist
        confirmation messages. Returns an API-shaped dict for POST .../message, or None.
        """
        from app.services.inbox_job_convert import (  # noqa: PLC0415
            try_convert_inbox_chat_on_approval,
        )

        return await try_convert_inbox_chat_on_approval(pool, chat_id, user_id, user_message)

    @classmethod
    async def process(cls, parsed: ParsedEmail) -> None:
        pool = await _get_pool()
        if not pool:
            logger.warning("InboxEngine: DB pool not available, skipping")
            return

        from_address = (parsed.from_address or "").strip().lower()
        if not from_address:
            logger.info("InboxEngine: skip empty from_address message_id=%s", parsed.message_id)
            return

        async with pool.acquire() as conn:
            # STAP 1 — Sender check (allowlist only; no record for unknown senders)
            row = await conn.fetchrow(
                """
                SELECT user_id, display_name FROM inbox_allowed_senders
                WHERE LOWER(email) = $1 AND is_active = true
                """,
                from_address,
            )
            if not row:
                logger.info("InboxEngine: ignored email from non-allowed sender %s", parsed.from_address)
                return

            user_id = str(row["user_id"])
            email_id = f"email:{parsed.message_id}"

            # Duplicate check
            existing = await conn.fetchrow(
                "SELECT email_id FROM inbound_emails WHERE message_id = $1",
                parsed.message_id,
            )
            if existing:
                logger.info(
                    "InboxEngine: duplicate message_id=%s existing_email_id=%s, skip",
                    parsed.message_id,
                    existing["email_id"],
                )
                return

            # STAP 2 — Insert inbound_emails (status new), then create direct chat
            await conn.execute(
                """
                INSERT INTO inbound_emails (
                    email_id, message_id, from_address, from_name, subject,
                    body_raw, body_clean, received_at, status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                email_id,
                parsed.message_id,
                parsed.from_address or "",
                parsed.from_name or "",
                parsed.subject or "",
                parsed.body_raw or "",
                parsed.body_clean or "",
                parsed.received_at,
                "new",
            )
            logger.info("InboxEngine: status → new for email_id=%s", email_id)
            await conn.execute(
                "UPDATE inbound_emails SET user_id = $1::uuid WHERE email_id = $2",
                user_id,
                email_id,
            )

            # CEO agent_id
            ceo_row = await conn.fetchrow(
                "SELECT agent_id FROM hired_agents WHERE LOWER(role) = 'ceo' LIMIT 1"
            )
            if not ceo_row:
                logger.error("InboxEngine: no CEO agent in hired_agents")
                await conn.execute(
                    "UPDATE inbound_emails SET status = $1, error_detail = $2 WHERE email_id = $3",
                    "error",
                    "CEO agent not found",
                    email_id,
                )
                logger.info("InboxEngine: status → error for email_id=%s (no CEO agent)", email_id)
                return

            ceo_agent_id = ceo_row["agent_id"]

            # Chat ID: same format as app/routes/agents.py (DC-YYYY-MM-###)
            prefix = datetime.now(timezone.utc).strftime("DC-%Y-%m-")
            num_row = await conn.fetchrow(
                """
                SELECT COALESCE(MAX(
                    CAST(NULLIF(SUBSTRING(chat_id FROM LENGTH($1) + 1), '') AS INTEGER)
                ), 0) + 1 AS next_num
                FROM direct_chats
                WHERE chat_id LIKE $1 || '%'
                """,
                prefix,
            )
            next_num = num_row["next_num"] if num_row else 1
            chat_id = f"{prefix}{next_num:03d}"

            await conn.execute(
                """
                INSERT INTO direct_chats (chat_id, agent_id, user_id, title, message_count, token_used)
                VALUES ($1, $2, $3, $4, 0, 0)
                """,
                chat_id,
                ceo_agent_id,
                user_id,
                (parsed.subject or "Email")[:500],
            )
            await conn.execute(
                "UPDATE inbound_emails SET chat_id = $1, status = $2 WHERE email_id = $3",
                chat_id,
                "analyzing",
                email_id,
            )
            logger.info("InboxEngine: status → analyzing for email_id=%s chat_id=%s", email_id, chat_id)

        # STAP 3 — First CEO message (outside conn so send_message can use its own pool)
        first_user_content = (
            f"Onderwerp: {parsed.subject or '—'}\n"
            f"Van: {parsed.from_name or '—'} ({parsed.from_address or '—'})\n\n"
            f"Inhoud:\n{(parsed.body_clean or '')[:BODY_TRUNCATE_CHARS]}"
        )
        extra_block = _ceo_inbox_system_block(
            parsed.subject or "",
            parsed.from_name or "",
            parsed.from_address or "",
            parsed.body_clean or "",
        )
        engine = DirectChatEngine()
        logger.info("InboxEngine: starting CEO analysis for email_id=%s chat_id=%s", email_id, chat_id)
        result = await engine.send_message(
            chat_id,
            first_user_content,
            extra_system_block=extra_block,
        )

        if result.get("error"):
            logger.warning("InboxEngine: CEO send_message failed for %s: %s", email_id, result.get("detail"))
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE inbound_emails SET status = $1, error_detail = $2 WHERE email_id = $3
                    """,
                    "error",
                    result.get("detail", "CEO response failed"),
                    email_id,
                )
                logger.info("InboxEngine: status → error for email_id=%s", email_id)
            return

        agent_response = result.get("agent_response") or ""
        plan_data = _extract_plan_block(agent_response)
        score_for_log: int | float | None = None
        if plan_data is not None:
            s = plan_data.get("completeness_score")
            if isinstance(s, (int, float)):
                score_for_log = s
        logger.info(
            "InboxEngine: CEO response received for email_id=%s, has_plan_block=%s, score=%s",
            email_id,
            plan_data is not None,
            score_for_log,
        )

        async with pool.acquire() as conn:
            if plan_data is not None:
                score = plan_data.get("completeness_score")
                if not isinstance(score, (int, float)):
                    score = None
                await conn.execute(
                    """
                    UPDATE inbound_emails SET status = $1, completeness_score = $2, processed_at = now()
                    WHERE email_id = $3
                    """,
                    "plan_ready",
                    score,
                    email_id,
                )
                logger.info("InboxEngine: status → plan_ready for email_id=%s", email_id)
            else:
                await conn.execute(
                    """
                    UPDATE inbound_emails SET status = $1, processed_at = now() WHERE email_id = $2
                    """,
                    "in_chat",
                    email_id,
                )
                logger.info("InboxEngine: status → in_chat for email_id=%s", email_id)
