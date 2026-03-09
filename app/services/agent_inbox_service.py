"""
Agent Inbox service — helpers voor agents om berichten te sturen.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def report_gap_to_ceo(
    conn,
    from_agent_id: str,
    subject: str,
    body: str,
    job_id: Optional[str] = None,
    urgency: str = "normal",
) -> None:
    """Worker/Talent agents gebruiken dit om gaps te rapporteren aan CEO."""
    await conn.execute(
        """
        INSERT INTO agent_inbox
        (from_agent_id, to_agent_id, subject, body, message_type, urgency, job_id)
        VALUES ($1, 'agent:ceo:mr-klein', $2, $3, 'gap_report', $4, $5)
        """,
        from_agent_id,
        subject,
        body,
        urgency,
        job_id,
    )
    logger.info("Gap reported to CEO from %s: %s", from_agent_id, subject[:50])
