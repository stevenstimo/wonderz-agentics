"""
Inbox Engine: allowed-sender check → direct chat with CEO → plan_ready / in_chat.

Emails NOT in inbox_allowed_senders are completely ignored (no DB write, no response).
"""

import json
import logging
from datetime import datetime, timezone

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

Als je genoeg informatie hebt (score >= 0.75):
Stel direct een plan voor. Sluit af met het plan als JSON blok in dit exacte formaat:

%%PLAN%%
{{"steps": [{{"agent_role": "...", "description": "..."}}], "completeness_score": 0.0, "assumptions": []}}
%%/PLAN%%

Als je onvoldoende informatie hebt (score < 0.75):
Stel maximaal 3 gerichte vragen. Geen plan nog."""


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
    async def process(cls, parsed: ParsedEmail) -> None:
        pool = await _get_pool()
        if not pool:
            logger.warning("InboxEngine: DB pool not available, skipping")
            return

        from_address = (parsed.from_address or "").strip().lower()
        if not from_address:
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
            return

        agent_response = result.get("agent_response") or ""
        plan_data = _extract_plan_block(agent_response)

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
                logger.info("InboxEngine: email_id=%s status=plan_ready", email_id)
            else:
                await conn.execute(
                    """
                    UPDATE inbound_emails SET status = $1, processed_at = now() WHERE email_id = $2
                    """,
                    "in_chat",
                    email_id,
                )
                logger.info("InboxEngine: email_id=%s status=in_chat", email_id)
