"""
Monitoring and observability endpoints.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from app.db import init_db_pool
from app.services.metrics_collector import MetricsCollector

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/health")
async def get_system_health():
    """
    Overall system health snapshot.

    Returns key metrics for dashboards.
    """
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    collector = MetricsCollector(pool)
    health = await collector.get_system_health()

    return health


@router.get("/agents/{agent_id}/performance")
async def get_agent_performance(agent_id: str, days: Optional[int] = 7):
    """Detailed performance metrics for agent."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    collector = MetricsCollector(pool)
    perf = await collector.get_agent_performance(agent_id, days)

    return perf


@router.get("/trends")
async def get_hourly_trends(hours: Optional[int] = 24):
    """Job completion trends by hour."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    collector = MetricsCollector(pool)
    trends = await collector.get_hourly_trends(hours)

    return {
        "period_hours": hours,
        "data": trends,
    }


@router.get("/dead-letters")
async def get_dead_letters():
    """Get jobs in dead letter queue (need manual intervention)."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        letters = await conn.fetch(
            """
            SELECT * FROM dead_letter_queue
            WHERE resolved_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
            """
        )

    return {
        "count": len(letters),
        "items": [dict(l) for l in letters],
    }
