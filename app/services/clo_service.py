"""
CLO Service — Chief Learning Officer
Strategische laag boven de HR Manager.
Geen pipeline-impact. Observeren, analyseren, adviseren en coördineren.
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


async def get_clo_dashboard(conn: asyncpg.Connection, period_days: int = 30) -> dict:
    """
    Aggregeer leer- en ontwikkeldata voor het CLO dashboard.
    """
    dev_points = await conn.fetch(
        """
        SELECT
            agent_id,
            COUNT(*)::bigint AS total_points,
            COUNT(*) FILTER (
                WHERE upper(trim(COALESCE(status, ''))) = 'OPEN'
            )::bigint AS open_points,
            COUNT(*) FILTER (
                WHERE upper(trim(COALESCE(status, ''))) = 'RESOLVED'
            )::bigint AS resolved_points,
            MAX(created_at) AS last_point_at
        FROM agent_improvements
        WHERE created_at >= now() - ($1 * interval '1 day')
          AND COALESCE(source, '') <> 'hr_blocked_job_notifier'
        GROUP BY agent_id
        ORDER BY open_points DESC
        LIMIT 10
        """,
        period_days,
    )

    newbie_pipeline = await conn.fetch(
        """
        SELECT
            status,
            COUNT(*)::bigint AS count,
            ROUND(AVG(readiness_score), 1) AS avg_readiness
        FROM newbies
        GROUP BY status
        ORDER BY count DESC
        """,
    )

    promotion_ready = await conn.fetch(
        """
        SELECT newbie_id, newbie_name, suggested_role, readiness_score, status
        FROM newbies
        WHERE readiness_score >= 70
          AND status IN ('in_training', 'ready')
        ORDER BY readiness_score DESC
        LIMIT 10
        """,
    )

    # readiness_score ontbreekt op sommige DB's; gebruik performance_score als proxy.
    low_readiness_agents = await conn.fetch(
        """
        SELECT
            h.agent_id,
            h.name,
            h.role,
            COALESCE(h.performance_score, 0)::double precision AS readiness_score,
            COUNT(ai.id) FILTER (
                WHERE upper(trim(COALESCE(ai.status, ''))) = 'OPEN'
            )::bigint AS open_dev_points
        FROM hired_agents h
        LEFT JOIN agent_improvements ai ON ai.agent_id = h.agent_id
        WHERE h.is_active = true
        GROUP BY h.agent_id, h.name, h.role, h.performance_score
        ORDER BY h.performance_score ASC NULLS LAST
        LIMIT 10
        """,
    )

    training_activity = await conn.fetch(
        """
        SELECT
            (date_trunc(
                'day',
                COALESCE(added_at, created_at) AT TIME ZONE 'UTC'
            ))::date AS dag,
            COUNT(*)::bigint AS chunks_added,
            COUNT(DISTINCT agent_id)::bigint AS agents_trained
        FROM agent_knowledge
        WHERE COALESCE(added_at, created_at) >= now() - INTERVAL '14 days'
          AND COALESCE(is_active, true) = true
        GROUP BY 1
        ORDER BY dag DESC
        """,
    )

    # Geen vaste 'hr_manager_scan' source in codebase: OPEN verbeterpunten buiten HR-blocked.
    cross_training = await conn.fetch(
        """
        SELECT
            ai.agent_id,
            ai.title,
            ai.summary AS description,
            ai.created_at,
            ai.source
        FROM agent_improvements ai
        WHERE upper(trim(COALESCE(ai.status, ''))) = 'OPEN'
          AND COALESCE(ai.source, '') <> 'hr_blocked_job_notifier'
          AND ai.created_at >= now() - ($1 * interval '1 day')
        ORDER BY ai.created_at DESC
        LIMIT 10
        """,
        period_days,
    )

    return {
        "period_days": period_days,
        "dev_points": [_row_dict(r) for r in dev_points],
        "newbie_pipeline": [_row_dict(r) for r in newbie_pipeline],
        "promotion_ready": [_row_dict(r) for r in promotion_ready],
        "low_readiness_agents": [_row_dict(r) for r in low_readiness_agents],
        "training_activity": [_row_dict(r) for r in training_activity],
        "cross_training": [_row_dict(r) for r in cross_training],
    }


async def get_agent_learning_profile(conn: asyncpg.Connection, agent_id: str) -> dict:
    """
    Gedetailleerd leerprofiel voor één agent.
    """
    agent = await conn.fetchrow(
        """
        SELECT agent_id, name, role, performance_score AS readiness_score
        FROM hired_agents
        WHERE agent_id = $1
        """,
        agent_id,
    )
    if not agent:
        return {}

    dev_points = await conn.fetch(
        """
        SELECT
            id,
            title,
            summary AS description,
            status,
            created_at,
            updated_at
        FROM agent_improvements
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 20
        """,
        agent_id,
    )

    knowledge_sources = await conn.fetch(
        """
        SELECT
            source_url,
            MAX(source_title) AS title,
            COUNT(*)::bigint AS chunk_count,
            MAX(COALESCE(added_at, created_at)) AS last_added
        FROM agent_knowledge
        WHERE agent_id = $1 AND COALESCE(is_active, true) = true
        GROUP BY source_url
        ORDER BY last_added DESC
        LIMIT 20
        """,
        agent_id,
    )

    return {
        "agent": _row_dict(agent),
        "dev_points": [_row_dict(r) for r in dev_points],
        "knowledge_sources": [_row_dict(r) for r in knowledge_sources],
    }
