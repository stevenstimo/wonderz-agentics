"""
CAO Service — Crew Analytics & Performance Monitoring
Geen pipeline-impact. Alleen observeren, analyseren en rapporteren.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

import asyncpg


def _row_dict(r: asyncpg.Record) -> Dict[str, Any]:
    d = dict(r)
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat() if v is not None else None
        else:
            out[k] = v
    return out


async def get_cao_dashboard(
    conn: asyncpg.Connection,
    period_days: int = 30,
) -> dict:
    """
    Aggregeer performance-inzichten voor het CAO dashboard.
    """
    job_stats = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_jobs,
            COUNT(*) FILTER (WHERE status = 'JOB_READY') AS completed,
            COUNT(*) FILTER (WHERE status = 'FAILED') AS failed,
            COUNT(*) FILTER (WHERE status = 'BLOCKED') AS blocked,
            COUNT(*) FILTER (WHERE status = 'NEEDS_CHANGES') AS needs_changes,
            ROUND(
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) / 60)::numeric, 1
            ) AS avg_duration_minutes
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
        """,
        period_days,
    )

    per_preset = await conn.fetch(
        """
        SELECT
            COALESCE(payload->>'preset_id', 'geen preset') AS preset,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'JOB_READY') AS completed,
            COUNT(*) FILTER (WHERE status = 'FAILED') AS failed,
            COUNT(*) FILTER (WHERE status = 'BLOCKED') AS blocked,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status = 'JOB_READY')
                / NULLIF(COUNT(*), 0), 1
            ) AS approval_rate
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
        GROUP BY payload->>'preset_id'
        ORDER BY total DESC
        LIMIT 10
        """,
        period_days,
    )

    per_agent = await conn.fetch(
        """
        SELECT
            js.agent_id,
            js.agent_role,
            COUNT(*) AS total_steps,
            COUNT(*) FILTER (WHERE js.status = 'completed') AS completed_steps,
            COUNT(*) FILTER (WHERE js.status = 'failed') AS failed_steps,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE js.status = 'completed')
                / NULLIF(COUNT(*), 0), 1
            ) AS success_rate
        FROM job_steps js
        JOIN jobs j ON j.id = js.job_id
        WHERE j.created_at >= now() - ($1 * interval '1 day')
          AND js.agent_id IS NOT NULL
        GROUP BY js.agent_id, js.agent_role
        ORDER BY total_steps DESC
        LIMIT 10
        """,
        period_days,
    )

    daily_trend = await conn.fetch(
        """
        SELECT
            (created_at AT TIME ZONE 'UTC')::date AS dag,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'JOB_READY') AS completed,
            COUNT(*) FILTER (WHERE status = 'FAILED') AS failed
        FROM jobs
        WHERE created_at >= now() - INTERVAL '14 days'
        GROUP BY (created_at AT TIME ZONE 'UTC')::date
        ORDER BY dag DESC
        """,
    )

    blocked_roles = await conn.fetch(
        """
        SELECT
            hr_missing_role_key AS role_key,
            MAX(title) AS role_label,
            COUNT(*)::bigint AS blocked_count
        FROM agent_improvements
        WHERE lower(coalesce(status, '')) = 'open'
          AND COALESCE(source, '') = 'hr_blocked_job_notifier'
          AND hr_missing_role_key IS NOT NULL
          AND btrim(hr_missing_role_key) <> ''
          AND created_at >= now() - ($1 * interval '1 day')
        GROUP BY hr_missing_role_key
        ORDER BY blocked_count DESC
        LIMIT 5
        """,
        period_days,
    )

    job_stats_d = _row_dict(job_stats) if job_stats else {}
    for k in ("total_jobs", "completed", "failed", "blocked", "needs_changes"):
        if k in job_stats_d and job_stats_d[k] is not None:
            job_stats_d[k] = int(job_stats_d[k])

    return {
        "period_days": period_days,
        "job_stats": job_stats_d,
        "per_preset": [_row_dict(r) for r in per_preset],
        "per_agent": [_row_dict(r) for r in per_agent],
        "daily_trend": [_row_dict(r) for r in daily_trend],
        "blocked_roles": [_row_dict(r) for r in blocked_roles],
    }
