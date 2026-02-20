"""HR Manager: Agent quality monitoring and training coordination."""

from __future__ import annotations

from typing import List, Dict, Optional, Any, Set, Tuple
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class HRManager:
    """Monitors agent performance and coordinates training."""

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

    async def _get_job_steps_agent_column(self, conn) -> Optional[str]:
        cols = await self._get_table_columns(conn, "job_steps")
        if "agent_id" in cols:
            return "agent_id"
        if "agent_role" in cols:
            return "agent_role"
        return None

    async def _get_job_steps_time_column(self, conn) -> Optional[str]:
        cols = await self._get_table_columns(conn, "job_steps")
        if "started_at" in cols:
            return "started_at"
        if "created_at" in cols:
            return "created_at"
        return None

    async def _get_development_points_agent_column(self, conn) -> Optional[str]:
        cols = await self._get_table_columns(conn, "development_points")
        if "agent_id" in cols:
            return "agent_id"
        if "agent_role" in cols:
            return "agent_role"
        return None

    def _calculate_impact(self, frequency: int) -> str:
        if frequency >= 10:
            return "high"
        if frequency >= 5:
            return "medium"
        return "low"

    async def scan_retry_patterns(self, since_days: int = 7) -> List[Dict[str, Any]]:
        """Scans job_steps for retry patterns in last N days."""
        if not self.pool:
            logger.warning("HR scan skipped: no DB pool")
            return []

        async with self.pool.acquire() as conn:
            agent_col = await self._get_job_steps_agent_column(conn)
            time_col = await self._get_job_steps_time_column(conn)
            job_cols = await self._get_table_columns(conn, "job_steps")

            if not agent_col or not time_col:
                logger.warning("HR scan skipped: job_steps missing agent/time columns")
                return []

            patterns: List[Dict[str, Any]] = []

            if "retry_count" in job_cols and "retry_reason" in job_cols:
                rows = await conn.fetch(
                    f"""
                    SELECT
                        {agent_col} as agent_key,
                        retry_reason,
                        COUNT(*) as frequency,
                        MAX({time_col}) as last_seen
                    FROM job_steps
                    WHERE retry_count > 0
                      AND retry_reason IS NOT NULL
                      AND {time_col} > NOW() - ($1 * INTERVAL '1 day')
                    GROUP BY {agent_col}, retry_reason
                    HAVING COUNT(*) >= 3
                    ORDER BY COUNT(*) DESC
                    """,
                    since_days,
                )

                for row in rows:
                    patterns.append({
                        "agent_id": row["agent_key"],
                        "retry_reason": row["retry_reason"],
                        "frequency": row["frequency"],
                        "last_seen": row["last_seen"],
                    })
            else:
                # Fallback: use failed status and error output when retry columns are unavailable
                rows = await conn.fetch(
                    f"""
                    SELECT
                        {agent_col} as agent_key,
                        COALESCE(
                            output->>'error',
                            CASE WHEN status = 'failed' THEN 'Step failed (no error detail)' ELSE NULL END
                        ) AS retry_reason,
                        COUNT(*) as frequency,
                        MAX({time_col}) as last_seen
                    FROM job_steps
                    WHERE status = 'failed'
                      AND {time_col} > NOW() - ($1 * INTERVAL '1 day')
                      AND {agent_col} IS NOT NULL
                    GROUP BY {agent_col}, retry_reason
                    HAVING COUNT(*) >= 3
                    ORDER BY COUNT(*) DESC
                    """,
                    since_days,
                )

                for row in rows:
                    patterns.append({
                        "agent_id": row["agent_key"],
                        "retry_reason": row["retry_reason"],
                        "frequency": row["frequency"],
                        "last_seen": row["last_seen"],
                    })

        logger.info("Found %s retry patterns in last %s days", len(patterns), since_days)
        return patterns

    async def _create_or_update_development_point(
        self,
        conn,
        agent_id: str,
        issue: str,
        frequency: int,
        evidence: Optional[str] = None,
        suggested_url: Optional[str] = None,
    ) -> Tuple[str, str]:
        columns = await self._get_table_columns(conn, "development_points")
        agent_col = await self._get_development_points_agent_column(conn)
        if not agent_col:
            raise RuntimeError("development_points missing agent_id/agent_role column")

        existing = await conn.fetchrow(
            f"""
            SELECT point_id, frequency, created_at
            FROM development_points
            WHERE {agent_col} = $1
              AND issue_description = $2
              AND status IN ('OPEN', 'AWAITING_APPROVAL')
            """,
            agent_id,
            issue,
        )

        if existing:
            set_clauses = ["frequency = frequency + $1"]
            if "updated_at" in columns:
                set_clauses.append("updated_at = NOW()")
            await conn.execute(
                f"""
                UPDATE development_points
                SET {', '.join(set_clauses)}
                WHERE point_id = $2
                """,
                frequency,
                existing["point_id"],
            )
            logger.info("Updated existing point %s frequency", existing["point_id"])
            return existing["point_id"], "updated"

        point_id = f"DP-{datetime.now().strftime('%Y-%m-%d')}-{agent_id[:8]}"
        if await conn.fetchval("SELECT 1 FROM development_points WHERE point_id = $1", point_id):
            point_id = f"{point_id}-{uuid.uuid4().hex[:4]}"

        impact = self._calculate_impact(frequency)

        insert_cols = ["point_id", agent_col, "issue_description", "frequency", "impact", "status", "proposed_by"]
        values: List[Any] = [point_id, agent_id, issue, frequency, impact, "OPEN", "hr-manager"]

        if evidence and "evidence_example" in columns:
            insert_cols.append("evidence_example")
            values.append(evidence)

        if suggested_url and "source_url" in columns:
            insert_cols.append("source_url")
            values.append(suggested_url)

        if "created_at" in columns:
            insert_cols.append("created_at")
            values.append(datetime.now())

        if "updated_at" in columns:
            insert_cols.append("updated_at")
            values.append(datetime.now())

        placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
        await conn.execute(
            f"""
            INSERT INTO development_points ({', '.join(insert_cols)})
            VALUES ({placeholders})
            """,
            *values,
        )

        logger.info("Created development point %s for %s", point_id, agent_id)
        return point_id, "created"

    async def create_development_point(
        self,
        agent_id: str,
        issue: str,
        frequency: int,
        evidence: Optional[str] = None,
        suggested_url: Optional[str] = None,
    ) -> str:
        """Creates a new development point for an agent. Returns point_id."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            point_id, _ = await self._create_or_update_development_point(
                conn,
                agent_id=agent_id,
                issue=issue,
                frequency=frequency,
                evidence=evidence,
                suggested_url=suggested_url,
            )
        return point_id

    async def process_retry_patterns(self, since_days: int = 7) -> Dict[str, int]:
        """Main workflow: scan patterns → create development points."""
        patterns = await self.scan_retry_patterns(since_days=since_days)

        created = 0
        updated = 0

        if not self.pool:
            return {"patterns_found": 0, "points_created": 0, "points_updated": 0}

        async with self.pool.acquire() as conn:
            for pattern in patterns:
                agent_id = pattern["agent_id"]
                issue = pattern["retry_reason"]
                freq = pattern["frequency"]
                evidence = f"Last seen: {pattern['last_seen']}"

                _, action = await self._create_or_update_development_point(
                    conn,
                    agent_id=agent_id,
                    issue=issue,
                    frequency=freq,
                    evidence=evidence,
                )
                if action == "created":
                    created += 1
                elif action == "updated":
                    updated += 1

        return {
            "patterns_found": len(patterns),
            "points_created": created,
            "points_updated": updated,
        }

    async def generate_weekly_report(self) -> Dict[str, Any]:
        """Generates weekly performance report for all agents."""
        if not self.pool:
            return {}

        async with self.pool.acquire() as conn:
            job_cols = await self._get_table_columns(conn, "job_steps")
            agent_col = await self._get_job_steps_agent_column(conn)
            time_col = await self._get_job_steps_time_column(conn)
            points_agent_col = await self._get_development_points_agent_column(conn)

            if not agent_col or not time_col or not points_agent_col:
                logger.warning("Weekly report skipped: missing columns")
                return {}

            agents = await conn.fetch(
                "SELECT agent_id, name, role FROM hired_agents WHERE status = 'active'"
            )

            report: Dict[str, Any] = {}

            for agent in agents:
                agent_id = agent["agent_id"]
                agent_key = agent_id

                points = await conn.fetch(
                    f"""
                    SELECT point_id, issue_description, impact, frequency
                    FROM development_points
                    WHERE {points_agent_col} = $1 AND status = 'OPEN'
                    ORDER BY
                        CASE impact
                            WHEN 'high' THEN 3
                            WHEN 'medium' THEN 2
                            WHEN 'low' THEN 1
                            WHEN 'HIGH' THEN 3
                            WHEN 'MEDIUM' THEN 2
                            WHEN 'LOW' THEN 1
                            ELSE 0
                        END DESC,
                        frequency DESC
                    """,
                    agent_key if points_agent_col == "agent_id" else agent["role"],
                )

                if "retry_count" in job_cols:
                    stats = await conn.fetchrow(
                        f"""
                        SELECT
                            COUNT(*) as total_steps,
                            SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END) as retry_steps,
                            AVG(CASE WHEN retry_count > 0 THEN retry_count ELSE 0 END) as avg_retries
                        FROM job_steps
                        WHERE {agent_col} = $1
                          AND {time_col} > NOW() - INTERVAL '7 days'
                        """,
                        agent_key if agent_col == "agent_id" else agent["role"],
                    )
                    retry_rate = (stats["retry_steps"] / stats["total_steps"]) if stats["total_steps"] else 0
                    avg_retries = float(stats["avg_retries"] or 0)
                else:
                    stats = await conn.fetchrow(
                        f"""
                        SELECT
                            COUNT(*) as total_steps,
                            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as retry_steps
                        FROM job_steps
                        WHERE {agent_col} = $1
                          AND {time_col} > NOW() - INTERVAL '7 days'
                        """,
                        agent_key if agent_col == "agent_id" else agent["role"],
                    )
                    retry_rate = (stats["retry_steps"] / stats["total_steps"]) if stats["total_steps"] else 0
                    avg_retries = 0

                report[agent_id] = {
                    "name": agent["name"],
                    "open_points": len(points),
                    "points": [dict(p) for p in points],
                    "total_steps": stats["total_steps"],
                    "failed_steps": stats["retry_steps"],
                    "success_rate": round(1 - retry_rate, 3),
                    "retry_rate": round(retry_rate, 3),
                    "avg_retries": round(avg_retries, 2),
                }

        return report

    async def approve_training(self, point_id: str, source_url: str, approved_by: str) -> Dict[str, Any]:
        """Approves a development point and starts training."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")

        async with self.pool.acquire() as conn:
            point = await conn.fetchrow(
                "SELECT * FROM development_points WHERE point_id = $1",
                point_id,
            )
            if not point:
                raise ValueError(f"Development point not found: {point_id}")

            columns = await self._get_table_columns(conn, "development_points")
            set_clauses = ["status = 'IN_TRAINING'"]
            params: List[Any] = []

            if "source_url" in columns:
                set_clauses.append("source_url = $1")
                params.append(source_url)

            if "approved_by" in columns:
                set_clauses.append(f"approved_by = ${len(params) + 1}")
                params.append(approved_by)

            if "updated_at" in columns:
                set_clauses.append("updated_at = NOW()")

            params.append(point_id)
            await conn.execute(
                f"""
                UPDATE development_points
                SET {', '.join(set_clauses)}
                WHERE point_id = ${len(params)}
                """,
                *params,
            )

        from app.services.training import train_agent_from_url

        try:
            result = await train_agent_from_url(
                pool=self.pool,
                agent_id=point.get("agent_id") or point.get("agent_role"),
                url=source_url,
                approved_by=approved_by,
            )

            async with self.pool.acquire() as conn:
                columns = await self._get_table_columns(conn, "development_points")
                set_clauses = ["status = 'RESOLVED'"]
                if "resolved_at" in columns:
                    set_clauses.append("resolved_at = NOW()")
                if "updated_at" in columns:
                    set_clauses.append("updated_at = NOW()")
                await conn.execute(
                    f"""
                    UPDATE development_points
                    SET {', '.join(set_clauses)}
                    WHERE point_id = $1
                    """,
                    point_id,
                )

            return {
                "point_id": point_id,
                "training_result": result,
                "status": "success",
            }

        except Exception as e:
            logger.error("Training failed for point %s: %s", point_id, e)

            async with self.pool.acquire() as conn:
                columns = await self._get_table_columns(conn, "development_points")
                set_clauses = ["status = 'OPEN'"]
                if "updated_at" in columns:
                    set_clauses.append("updated_at = NOW()")
                await conn.execute(
                    f"""
                    UPDATE development_points
                    SET {', '.join(set_clauses)}
                    WHERE point_id = $1
                    """,
                    point_id,
                )

            return {
                "point_id": point_id,
                "error": str(e),
                "status": "failed",
            }

    async def scan_job_steps(self, since_days: int = 7) -> Dict[str, int]:
        """Backward-compatible wrapper around retry pattern processing."""
        result = await self.process_retry_patterns(since_days=since_days)
        return {
            "scanned": result["patterns_found"],
            "points_created": result["points_created"],
            "points_updated": result["points_updated"],
        }

    async def get_development_points(
        self,
        agent_id: Optional[str] = None,
        agent_role: Optional[str] = None,
        impact: Optional[str] = None,
        status: str = "OPEN",
    ) -> List[Dict[str, Any]]:
        """List development points with optional filters."""
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            columns = await self._get_table_columns(conn, "development_points")
            agent_col = await self._get_development_points_agent_column(conn)

            query = "SELECT * FROM development_points WHERE 1=1"
            params: List[Any] = []
            idx = 1

            if status:
                query += f" AND status = ${idx}"
                params.append(status)
                idx += 1

            if impact:
                query += f" AND impact = ${idx}"
                params.append(impact)
                idx += 1

            if agent_col:
                if agent_id and agent_col == "agent_id":
                    query += f" AND {agent_col} = ${idx}"
                    params.append(agent_id)
                    idx += 1
                elif agent_role and agent_col == "agent_role":
                    query += f" AND {agent_col} = ${idx}"
                    params.append(agent_role)
                    idx += 1

            query += " ORDER BY created_at DESC" if "created_at" in columns else ""

            rows = await conn.fetch(query, *params)

        points: List[Dict[str, Any]] = []
        for r in rows:
            data = dict(r)
            if "created_at" in data and data.get("created_at"):
                data["created_at"] = data["created_at"].isoformat()
            if "updated_at" in data and data.get("updated_at"):
                data["updated_at"] = data["updated_at"].isoformat()
            if "resolved_at" in data and data.get("resolved_at"):
                data["resolved_at"] = data["resolved_at"].isoformat()
            if "id" in data:
                data["id"] = str(data["id"])
            points.append(data)

        return points

    async def resolve_point(self, point_id: str, resolution: str) -> bool:
        """Mark a development point as resolved."""
        if not self.pool:
            return False

        async with self.pool.acquire() as conn:
            columns = await self._get_table_columns(conn, "development_points")
            set_clauses = ["status = $1"]
            params: List[Any] = ["RESOLVED"]
            idx = 2

            if resolution and "resolution" in columns:
                set_clauses.append(f"resolution = ${idx}")
                params.append(resolution)
                idx += 1

            if "resolved_at" in columns:
                set_clauses.append("resolved_at = NOW()")

            if "updated_at" in columns:
                set_clauses.append("updated_at = NOW()")

            params.append(point_id)
            result = await conn.execute(
                f"""
                UPDATE development_points
                SET {', '.join(set_clauses)}
                WHERE point_id = ${idx}
                """,
                *params,
            )

        return result != "UPDATE 0"

    async def dismiss_point(self, point_id: str) -> bool:
        """Dismiss a development point."""
        if not self.pool:
            return False

        async with self.pool.acquire() as conn:
            columns = await self._get_table_columns(conn, "development_points")
            set_clauses = ["status = $1"]
            params: List[Any] = ["DISMISSED"]
            idx = 2

            if "updated_at" in columns:
                set_clauses.append("updated_at = NOW()")

            params.append(point_id)
            result = await conn.execute(
                f"""
                UPDATE development_points
                SET {', '.join(set_clauses)}
                WHERE point_id = ${idx}
                """,
                *params,
            )

        return result != "UPDATE 0"
