"""CEO Dashboard API. Fase B — docs/cursor/02_dashboard_newbies_navigation.md."""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _serialize_row(r):
    if r is None:
        return None
    d = dict(r)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif hasattr(v, "hex"):
            d[k] = str(v)
    return d


@router.get("/ceo")
async def get_ceo_dashboard():
    """
    CEO Dashboard: crew status, operational today, agent health, recent activity.
    Ref: docs/cursor/02_dashboard_newbies_navigation.md Fase B.
    """
    pool = await get_db()
    today = date.today()
    async with pool.acquire() as conn:
        # Blok 1 — Crew Status
        active_agents = await conn.fetchval(
            "SELECT COUNT(*) FROM hired_agents WHERE is_active = true"
        ) or 0
        newbies_in_training = await conn.fetchval(
            "SELECT COUNT(*) FROM newbies WHERE status = 'in_training'"
        ) or 0
        newbies_ready = await conn.fetchval(
            "SELECT COUNT(*) FROM newbies WHERE status = 'ready'"
        ) or 0
        suspended_agents = await conn.fetchval(
            "SELECT COUNT(*) FROM hired_agents WHERE is_suspended = true"
        ) or 0

        # Blok 2 — Operationeel vandaag (jobs)
        jobs_running = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE status = 'RUNNING'"
        ) or 0
        jobs_completed_today = await conn.fetchval(
            """
            SELECT COUNT(*) FROM jobs
            WHERE status = 'COMPLETED' AND (
              completed_at::date = $1::date
              OR (completed_at IS NULL AND updated_at::date = $1::date)
            )
            """,
            today,
        ) or 0
        jobs_awaiting_approval = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE status = 'JOB_READY'"
        ) or 0
        jobs_failed = await conn.fetchval(
            """
            SELECT COUNT(*) FROM jobs
            WHERE status IN ('FAILED', 'BUDGET_EXCEEDED')
            """
        ) or 0

        # Blok 3 — Agent Health (development_points, training_requests, agents with >3 open points)
        open_development_points = await conn.fetchval(
            """
            SELECT COUNT(*) FROM development_points
            WHERE LOWER(COALESCE(status, '')) IN ('open', '')
            OR status = 'OPEN'
            """
        ) or 0
        training_requests_open = 0
        try:
            training_requests_open = await conn.fetchval(
                """
                SELECT COUNT(*) FROM training_requests
                WHERE LOWER(COALESCE(status, '')) IN ('pending', 'training_requested')
                """
            ) or 0
        except Exception:
            pass
        # Agents met meer dan 3 open development points
        high_retry_rows = await conn.fetch(
            """
            SELECT agent_id, COUNT(*) AS cnt FROM development_points
            WHERE LOWER(COALESCE(status, '')) IN ('open', '') OR status = 'OPEN'
            GROUP BY agent_id HAVING COUNT(*) > 3
            """
        )
        high_retry_agents = [r["agent_id"] for r in high_retry_rows] if high_retry_rows else []

        # Blok 4 — Recente activiteit
        recent_jobs_rows = await conn.fetch(
            """
            SELECT id, status, completed_at, updated_at
            FROM jobs WHERE status = 'COMPLETED'
            ORDER BY COALESCE(completed_at, updated_at) DESC NULLS LAST
            LIMIT 5
            """
        )
        recent_jobs = [_serialize_row(r) for r in recent_jobs_rows] if recent_jobs_rows else []
        recent_dp_rows = await conn.fetch(
            """
            SELECT point_id, agent_id, agent_role, issue_description, impact, status, created_at
            FROM development_points
            ORDER BY created_at DESC NULLS LAST
            LIMIT 3
            """
        )
        recent_development_points = [_serialize_row(r) for r in recent_dp_rows] if recent_dp_rows else []

    return {
        "crew_status": {
            "active_agents": active_agents,
            "newbies_in_training": newbies_in_training,
            "newbies_ready": newbies_ready,
            "suspended_agents": suspended_agents,
        },
        "operational": {
            "jobs_running": jobs_running,
            "jobs_completed_today": jobs_completed_today,
            "jobs_awaiting_approval": jobs_awaiting_approval,
            "jobs_failed": jobs_failed,
        },
        "agent_health": {
            "open_development_points": open_development_points,
            "training_requests_open": training_requests_open,
            "high_retry_agents": high_retry_agents,
        },
        "recent_activity": {
            "recent_jobs": recent_jobs,
            "recent_development_points": recent_development_points,
        },
    }
