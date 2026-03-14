"""High-level intelligence overview metrics."""
from typing import Optional
from fastapi import APIRouter, HTTPException
from app.db import init_db_pool

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


async def _table_exists(conn, table_name: str) -> bool:
    return await conn.fetchval(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table_name,
    ) is not None


async def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return await conn.fetchval(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1 AND column_name = $2
        """,
        table_name,
        column_name,
    ) is not None


async def _confidence_stats(conn, table_name: str) -> dict:
    if not await _table_exists(conn, table_name):
        return {"count": 0, "avg": None, "min": None, "max": None}
    if not await _column_exists(conn, table_name, "confidence_score"):
        return {"count": 0, "avg": None, "min": None, "max": None}

    row = await conn.fetchrow(
        f"""
        SELECT
            COUNT(confidence_score) as count,
            AVG(confidence_score) as avg,
            MIN(confidence_score) as min,
            MAX(confidence_score) as max
        FROM {table_name}
        WHERE confidence_score IS NOT NULL
        """
    )
    if not row:
        return {"count": 0, "avg": None, "min": None, "max": None}

    return {
        "count": int(row["count"] or 0),
        "avg": float(row["avg"]) if row["avg"] is not None else None,
        "min": float(row["min"]) if row["min"] is not None else None,
        "max": float(row["max"]) if row["max"] is not None else None,
    }


def _combine_confidence_stats(*stats: dict) -> dict:
    total_count = sum(s.get("count", 0) or 0 for s in stats)
    if total_count == 0:
        return {"count": 0, "avg": None, "min": None, "max": None}

    weighted_sum = 0.0
    mins = []
    maxs = []
    for s in stats:
        count = s.get("count", 0) or 0
        avg = s.get("avg")
        if count and avg is not None:
            weighted_sum += avg * count
        if s.get("min") is not None:
            mins.append(s["min"])
        if s.get("max") is not None:
            maxs.append(s["max"])

    return {
        "count": total_count,
        "avg": round(weighted_sum / total_count, 4) if total_count else None,
        "min": min(mins) if mins else None,
        "max": max(maxs) if maxs else None,
    }


@router.get("/overview")
async def intelligence_overview():
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        agents_count = 0
        if await _table_exists(conn, "hired_agents"):
            agents_count = await conn.fetchval("SELECT COUNT(*) FROM hired_agents") or 0

        jobs_completed = 0
        if await _table_exists(conn, "jobs"):
            if await _column_exists(conn, "jobs", "status"):
                jobs_completed = await conn.fetchval(
                    "SELECT COUNT(*) FROM jobs WHERE status = 'COMPLETED'"
                ) or 0

        lessons_total = 0
        lessons_propagated = 0
        if await _table_exists(conn, "learning_events"):
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COALESCE(SUM(propagated_to), 0) as propagated
                FROM learning_events
                """
            )
            if row:
                lessons_total = row["total"] or 0
                lessons_propagated = row["propagated"] or 0

        training_confidence = await _confidence_stats(conn, "training_requests")
        development_confidence = await _confidence_stats(conn, "agent_improvements")
        overall_confidence = _combine_confidence_stats(
            training_confidence, development_confidence
        )

    return {
        "agents": int(agents_count),
        "jobs_completed": int(jobs_completed),
        "lessons_learned": {
            "total": int(lessons_total),
            "propagated_to": int(lessons_propagated),
        },
        "confidence_scores": {
            "training_requests": training_confidence,
            "development_points": development_confidence,
            "overall": overall_confidence,
        },
    }
