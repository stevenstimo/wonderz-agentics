"""
CDO Service — Chief Delivery Officer
Fase 1: monitoring alignment intake vs output (geen pipeline-impact).
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


async def get_cdo_dashboard(conn: asyncpg.Connection, period_days: int = 30) -> dict:
    """Delivery-overzicht voor de CDO."""

    delivered_jobs = await conn.fetch(
        """
        SELECT
            id, title, created_at, updated_at,
            payload->>'preset_id' AS preset_id,
            payload->>'client_name' AS client_name,
            EXTRACT(EPOCH FROM (updated_at - created_at)) / 60 AS duration_minutes
        FROM jobs
        WHERE upper(trim(COALESCE(status, ''))) = 'JOB_READY'
          AND created_at >= now() - ($1 * interval '1 day')
        ORDER BY updated_at DESC
        LIMIT 20
        """,
        period_days,
    )

    revision_jobs = await conn.fetch(
        """
        SELECT id, title, created_at, updated_at,
               payload->>'client_name' AS client_name,
               payload->>'preset_id' AS preset_id
        FROM jobs
        WHERE upper(trim(COALESCE(status, ''))) = 'NEEDS_CHANGES'
          AND created_at >= now() - ($1 * interval '1 day')
        ORDER BY updated_at DESC
        LIMIT 10
        """,
        period_days,
    )

    delivery_stats = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE upper(trim(COALESCE(status, ''))) = 'JOB_READY')::bigint AS delivered,
            COUNT(*) FILTER (WHERE upper(trim(COALESCE(status, ''))) = 'NEEDS_CHANGES')::bigint AS revisions,
            COUNT(*) FILTER (WHERE upper(trim(COALESCE(status, ''))) = 'FAILED')::bigint AS failed,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE upper(trim(COALESCE(status, ''))) = 'JOB_READY')
                / NULLIF(
                    COUNT(*) FILTER (
                        WHERE upper(trim(COALESCE(status, ''))) IN ('JOB_READY', 'NEEDS_CHANGES', 'FAILED')
                    ),
                    0
                ),
                1
            ) AS first_time_right_rate,
            ROUND(
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) / 60)
                FILTER (WHERE upper(trim(COALESCE(status, ''))) = 'JOB_READY')::numeric,
                1
            ) AS avg_delivery_minutes
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
        """,
        period_days,
    )

    per_client = await conn.fetch(
        """
        SELECT
            payload->>'client_name' AS client_name,
            COUNT(*)::bigint AS total,
            COUNT(*) FILTER (WHERE upper(trim(COALESCE(status, ''))) = 'JOB_READY')::bigint AS delivered,
            COUNT(*) FILTER (WHERE upper(trim(COALESCE(status, ''))) = 'NEEDS_CHANGES')::bigint AS revisions,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE upper(trim(COALESCE(status, ''))) = 'JOB_READY')
                / NULLIF(COUNT(*), 0),
                1
            ) AS delivery_rate
        FROM jobs
        WHERE created_at >= now() - ($1 * interval '1 day')
          AND COALESCE(trim(payload->>'client_name'), '') <> ''
        GROUP BY payload->>'client_name'
        ORDER BY total DESC
        LIMIT 10
        """,
        period_days,
    )

    return {
        "period_days": period_days,
        "delivery_stats": _row_dict(delivery_stats) if delivery_stats else {},
        "delivered_jobs": [_row_dict(r) for r in delivered_jobs],
        "revision_jobs": [_row_dict(r) for r in revision_jobs],
        "per_client": [_row_dict(r) for r in per_client],
    }
