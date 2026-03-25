"""
Auto-unblock BLOCKED jobs na hire.

Pattern: blocked jobs on preset/resource gaps → when required hired_agents exist,
zet job terug naar INTAKE_CLARIFICATION.
"""

from __future__ import annotations

import logging
import json
from typing import Any, Optional

import asyncpg

from app.orchestration.ceo_intent import check_resources, detect_job_type
from models.unified import JobStatus

logger = logging.getLogger(__name__)


async def unblock_blocked_jobs_after_hire(conn: asyncpg.Connection) -> int:
    """
    Check all BLOCKED jobs that were gated by CEO preset/resources.
    If resources are now complete, job returns to INTAKE_CLARIFICATION.
    """
    rows = await conn.fetch(
        """
        SELECT id, job_post, payload
        FROM jobs
        WHERE status = 'BLOCKED'
          AND payload->>'ceo_preset_blocked' = 'true'
        ORDER BY updated_at DESC NULLS LAST
        """
    )
    if not rows:
        return 0

    updated = 0
    for job in rows:
        jid = str(job["id"])
        job_post = job.get("job_post") or ""

        try:
            preset_id = await detect_job_type(conn, job_post)
        except Exception:
            logger.exception("[job_unblock] detect_job_type failed job=%s", jid)
            continue

        if not preset_id:
            continue

        try:
            report = await check_resources(conn, preset_id)
        except Exception:
            logger.exception("[job_unblock] check_resources failed job=%s preset=%s", jid, preset_id)
            continue

        if not report.get("ready"):
            continue

        # Unblock job.
        await conn.execute(
            """
            UPDATE jobs
            SET status = $1,
                payload = COALESCE(payload, '{}'::jsonb)
                          - 'ceo_preset_blocked'
                          - 'missing_roles'
                          - 'block_reason',
                updated_at = now()
            WHERE id = $2::uuid
            """,
            JobStatus.INTAKE_CLARIFICATION.value,
            jid,
        )

        # Resolve HR blocked-job improvements for this job.
        # We mark all OPEN items created by the notifier as RESOLVED.
        needle = f'%\"job_id\":\"{jid}\"%'
        try:
            await conn.execute(
                """
                UPDATE agent_improvements
                SET status = 'RESOLVED',
                    updated_at = now()
                WHERE source = 'hr_blocked_job_notifier'
                  AND status = 'OPEN'
                  AND details::text LIKE $1
                """,
                needle,
            )
        except Exception:
            logger.exception("[job_unblock] failed to resolve agent_improvements job=%s", jid)

        updated += 1

    return updated

