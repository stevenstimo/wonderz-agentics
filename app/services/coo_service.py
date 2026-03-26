"""
COO Service — Chief Operating Officer
Fase 1: monitoring en rapportage van de productie-pipeline (geen pipeline-impact).
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


async def get_coo_dashboard(conn: asyncpg.Connection, period_days: int = 30) -> dict:
    """Productie-overzicht voor de COO."""

    active_jobs = await conn.fetch(
        """
        SELECT id, title, status, created_at, updated_at,
               payload->>'preset_id' AS preset_id,
               payload->>'client_name' AS client_name
        FROM jobs
        WHERE upper(trim(status)) = 'RUNNING'
        ORDER BY created_at ASC
        LIMIT 20
        """,
    )

    status_breakdown = await conn.fetch(
        """
        SELECT status, COUNT(*)::bigint AS count,
               ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) / 60)::numeric, 1) AS avg_minutes
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
        GROUP BY status
        ORDER BY count DESC
        """,
        period_days,
    )

    step_performance = await conn.fetch(
        """
        SELECT
            js.agent_role,
            COUNT(*)::bigint AS total_steps,
            COUNT(*) FILTER (WHERE lower(trim(COALESCE(js.status, ''))) = 'completed')::bigint AS completed,
            COUNT(*) FILTER (WHERE lower(trim(COALESCE(js.status, ''))) = 'failed')::bigint AS failed,
            ROUND(AVG(js.tokens_used)::numeric, 0) AS avg_tokens
        FROM job_steps js
        JOIN jobs j ON j.id = js.job_id
        WHERE j.created_at >= now() - ($1 * interval '1 day')
          AND js.agent_role IS NOT NULL
        GROUP BY js.agent_role
        ORDER BY total_steps DESC
        """,
        period_days,
    )

    recent_failures = await conn.fetch(
        """
        SELECT js.job_id, js.step_name, js.agent_role, js.status,
               COALESCE(js.error_log, '') AS error_message,
               js.created_at
        FROM job_steps js
        WHERE lower(trim(COALESCE(js.status, ''))) = 'failed'
          AND js.created_at >= now() - ($1 * interval '1 day')
        ORDER BY js.created_at DESC
        LIMIT 10
        """,
        period_days,
    )

    return {
        "period_days": period_days,
        "active_jobs": [_row_dict(r) for r in active_jobs],
        "status_breakdown": [_row_dict(r) for r in status_breakdown],
        "step_performance": [_row_dict(r) for r in step_performance],
        "recent_failures": [_row_dict(r) for r in recent_failures],
    }
