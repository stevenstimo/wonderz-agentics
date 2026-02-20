"""
Real-time metrics collection for monitoring.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and aggregates system metrics.
    """

    def __init__(self, pool):
        self.pool = pool
        self._columns_cache: Dict[str, Set[str]] = {}

    async def _get_table_columns(self, conn, table_name: str) -> Set[str]:
        if table_name in self._columns_cache:
            return self._columns_cache[table_name]
        rows = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            """,
            table_name,
        )
        cols = {r["column_name"] for r in rows}
        self._columns_cache[table_name] = cols
        return cols

    async def _get_time_column(self, conn, table_name: str, candidates: List[str]) -> Optional[str]:
        cols = await self._get_table_columns(conn, table_name)
        for col in candidates:
            if col in cols:
                return col
        return None

    async def _get_agent_column(self, conn) -> Optional[str]:
        cols = await self._get_table_columns(conn, "job_steps")
        if "agent_id" in cols:
            return "agent_id"
        if "agent_role" in cols:
            return "agent_role"
        return None

    async def _get_job_tokens_column(self, conn) -> Optional[str]:
        cols = await self._get_table_columns(conn, "jobs")
        if "token_used_total" in cols:
            return "token_used_total"
        if "tokens_used" in cols:
            return "tokens_used"
        return None

    async def _get_step_tokens_column(self, conn) -> Optional[str]:
        cols = await self._get_table_columns(conn, "job_steps")
        if "token_usage" in cols:
            return "token_usage"
        if "tokens_used" in cols:
            return "tokens_used"
        return None

    async def _get_latency_column(self, conn) -> Optional[str]:
        cols = await self._get_table_columns(conn, "job_steps")
        if "latency_ms" in cols:
            return "latency_ms"
        if "timing_ms" in cols:
            return "timing_ms"
        return None

    async def get_system_health(self) -> Dict:
        """
        Overall system health snapshot.

        Returns:
        - Job success rate (last 24h)
        - Active agents count
        - Error rate
        - Average response time
        - Token usage
        """
        async with self.pool.acquire() as conn:
            jobs_time_col = await self._get_time_column(conn, "jobs", ["created_at", "updated_at"])
            steps_time_col = await self._get_time_column(conn, "job_steps", ["started_at", "created_at"])
            job_tokens_col = await self._get_job_tokens_column(conn)
            latency_col = await self._get_latency_column(conn)

            jobs_time_filter = f"WHERE {jobs_time_col} > NOW() - INTERVAL '24 hours'" if jobs_time_col else ""
            steps_time_filter = f"WHERE {steps_time_col} > NOW() - INTERVAL '24 hours'" if steps_time_col else ""

            job_tokens_expr = f"AVG({job_tokens_col})" if job_tokens_col else "0"
            latency_expr = f"AVG({latency_col})" if latency_col else "0"

            job_stats = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                    {job_tokens_expr} as avg_tokens
                FROM jobs
                {jobs_time_filter}
                """
            )

            agent_cols = await self._get_table_columns(conn, "hired_agents")
            has_status = "status" in agent_cols
            has_suspended = "is_suspended" in agent_cols

            agent_stats = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) as total_agents,
                    {("SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active" if has_status else "0 as active")},
                    {("SUM(CASE WHEN is_suspended THEN 1 ELSE 0 END) as suspended" if has_suspended else "0 as suspended")}
                FROM hired_agents
                """
            )

            step_cols = await self._get_table_columns(conn, "job_steps")
            retry_expr = "SUM(retry_count)" if "retry_count" in step_cols else "0"

            error_stats = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) as total_steps,
                    {retry_expr} as total_retries,
                    {latency_expr} as avg_latency
                FROM job_steps
                {steps_time_filter}
                """
            )

            total_jobs = job_stats["total_jobs"] or 0
            completed = job_stats["completed"] or 0
            total_steps = error_stats["total_steps"] or 0
            total_retries = error_stats["total_retries"] or 0

            success_rate = (completed / total_jobs) if total_jobs > 0 else 0
            error_rate = (total_retries / total_steps) if total_steps > 0 else 0

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "health_score": self._calculate_health_score(success_rate, error_rate),
                "jobs": {
                    "total_24h": total_jobs,
                    "completed": completed,
                    "failed": job_stats["failed"] or 0,
                    "success_rate": round(success_rate, 3),
                    "avg_tokens": int(job_stats["avg_tokens"] or 0),
                },
                "agents": {
                    "total": agent_stats["total_agents"] or 0,
                    "active": agent_stats["active"] or 0,
                    "suspended": agent_stats["suspended"] or 0,
                },
                "performance": {
                    "error_rate": round(error_rate, 3),
                    "avg_latency_ms": int(error_stats["avg_latency"] or 0),
                    "total_retries": total_retries or 0,
                },
            }

    def _calculate_health_score(self, success_rate: float, error_rate: float) -> int:
        """
        Health score 0-100.

        - 90-100: Excellent
        - 70-89: Good
        - 50-69: Warning
        - <50: Critical
        """
        score = 100
        score -= (1 - success_rate) * 50
        score -= error_rate * 30
        return max(0, min(100, int(score)))

    async def get_agent_performance(self, agent_id: str, days: int = 7) -> Dict:
        """Detailed performance metrics for single agent."""
        async with self.pool.acquire() as conn:
            agent_col = await self._get_agent_column(conn)
            time_col = await self._get_time_column(conn, "job_steps", ["started_at", "created_at"])
            step_token_col = await self._get_step_tokens_column(conn)
            job_cols = await self._get_table_columns(conn, "jobs")
            step_cols = await self._get_table_columns(conn, "job_steps")

            if not agent_col or not time_col:
                logger.warning("Agent performance skipped: missing agent/time columns on job_steps")
                return {
                    "agent_id": agent_id,
                    "period_days": days,
                    "jobs_worked": 0,
                    "success_rate": 0,
                    "total_retries": 0,
                    "avg_latency_ms": 0,
                    "total_tokens": 0,
                    "top_errors": [],
                }

            success_expr = (
                "AVG(CASE WHEN j.status = 'COMPLETED' THEN 1 ELSE 0 END)"
                if "status" in job_cols
                else "AVG(CASE WHEN js.status = 'success' THEN 1 ELSE 0 END)"
            )
            token_expr = f"SUM(js.{step_token_col})" if step_token_col else "0"
            latency_col = await self._get_latency_column(conn)
            latency_expr = f"AVG(js.{latency_col})" if latency_col else "0"
            retry_expr = "SUM(js.retry_count)" if "retry_count" in step_cols else "0"

            stats = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(DISTINCT js.job_id) as jobs_worked,
                    {success_expr} as success_rate,
                    {retry_expr} as total_retries,
                    {latency_expr} as avg_latency,
                    {token_expr} as total_tokens
                FROM job_steps js
                LEFT JOIN jobs j ON js.job_id = j.id
                WHERE js.{agent_col} = $1
                  AND js.{time_col} > NOW() - INTERVAL '{days} days'
                """,
                agent_id,
            )

            if "retry_reason" in step_cols:
                errors = await conn.fetch(
                    f"""
                    SELECT retry_reason, COUNT(*) as count
                    FROM job_steps
                    WHERE {agent_col} = $1
                      AND retry_count > 0
                      AND {time_col} > NOW() - INTERVAL '{days} days'
                    GROUP BY retry_reason
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                    """,
                    agent_id,
                )
            else:
                errors = await conn.fetch(
                    f"""
                    SELECT COALESCE(output->>'error', 'unknown') as retry_reason, COUNT(*) as count
                    FROM job_steps
                    WHERE {agent_col} = $1
                      AND status = 'failed'
                      AND {time_col} > NOW() - INTERVAL '{days} days'
                    GROUP BY COALESCE(output->>'error', 'unknown')
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                    """,
                    agent_id,
                )

        return {
            "agent_id": agent_id,
            "period_days": days,
            "jobs_worked": stats["jobs_worked"] or 0,
            "success_rate": round(float(stats["success_rate"] or 0), 3),
            "total_retries": stats["total_retries"] or 0,
            "avg_latency_ms": int(stats["avg_latency"] or 0),
            "total_tokens": stats["total_tokens"] or 0,
            "top_errors": [
                {"reason": e["retry_reason"], "count": e["count"]}
                for e in errors
            ],
        }

    async def get_hourly_trends(self, hours: int = 24) -> List[Dict]:
        """Job completion trends by hour."""
        async with self.pool.acquire() as conn:
            time_col = await self._get_time_column(conn, "jobs", ["created_at", "updated_at"])
            token_col = await self._get_job_tokens_column(conn)

            if not time_col:
                return []

            token_expr = f"AVG({token_col})" if token_col else "0"
            trends = await conn.fetch(
                f"""
                SELECT
                    DATE_TRUNC('hour', {time_col}) as hour,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                    {token_expr} as avg_tokens
                FROM jobs
                WHERE {time_col} > NOW() - INTERVAL '{hours} hours'
                GROUP BY DATE_TRUNC('hour', {time_col})
                ORDER BY hour DESC
                """
            )

        return [
            {
                "hour": t["hour"].isoformat(),
                "total": t["total"],
                "completed": t["completed"],
                "failed": t["failed"],
                "success_rate": round(t["completed"] / t["total"], 3) if t["total"] > 0 else 0,
                "avg_tokens": int(t["avg_tokens"] or 0),
            }
            for t in trends
        ]
