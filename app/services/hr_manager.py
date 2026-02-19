"""HR Manager: Detects agent problems and creates development points.

Scans job_steps for failure patterns and creates actionable development
points with impact scoring. Generates weekly performance reports per agent.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class HRManager:
    """Detecteert agent problemen en maakt development points aan."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def scan_job_steps(self, since_days: int = 7) -> Dict[str, Any]:
        """Scan job_steps for retry/failure patterns.

        Finds agents with >=3 failures in the given period and creates
        or updates development points.
        """
        if not self.db_pool:
            logger.warning("HR scan skipped: no DB pool")
            return {"scanned": 0, "points_created": 0, "points_updated": 0}

        created = 0
        updated = 0

        async with self.db_pool.acquire() as conn:
            # Find failure patterns: same agent_role + similar error, >= 3 occurrences
            patterns = await conn.fetch("""
                SELECT
                    agent_role,
                    COALESCE(
                        output->>'error',
                        CASE WHEN status = 'failed' THEN 'Step failed (no error detail)' ELSE NULL END
                    ) AS error_text,
                    COUNT(*) AS frequency,
                    array_agg(DISTINCT job_id::text) AS affected_jobs
                FROM job_steps
                WHERE
                    status = 'failed'
                    AND created_at > NOW() - make_interval(days => $1)
                    AND agent_role IS NOT NULL
                    AND agent_role != 'orchestrator'
                GROUP BY agent_role, error_text
                HAVING COUNT(*) >= 3
            """, since_days)

            for pattern in patterns:
                error_text = pattern['error_text'] or 'Unknown failure'
                result = await self._create_or_update_point(
                    conn,
                    agent_role=pattern['agent_role'],
                    issue=error_text[:500],
                    frequency=pattern['frequency'],
                    evidence=pattern['affected_jobs'][:5]
                )
                if result == 'created':
                    created += 1
                elif result == 'updated':
                    updated += 1

            # Also scan for high retry rates (agents that succeed but need many attempts)
            retry_patterns = await conn.fetch("""
                SELECT
                    agent_role,
                    COUNT(*) AS total_attempts,
                    COUNT(DISTINCT job_id) AS unique_jobs
                FROM job_steps
                WHERE
                    created_at > NOW() - make_interval(days => $1)
                    AND agent_role IS NOT NULL
                    AND agent_role != 'orchestrator'
                GROUP BY agent_role
                HAVING COUNT(*) > COUNT(DISTINCT job_id) * 2
            """, since_days)

            for rp in retry_patterns:
                retry_rate = rp['total_attempts'] / max(rp['unique_jobs'], 1)
                if retry_rate >= 3:
                    result = await self._create_or_update_point(
                        conn,
                        agent_role=rp['agent_role'],
                        issue=f"High retry rate: {retry_rate:.1f}x attempts per job ({rp['total_attempts']} attempts across {rp['unique_jobs']} jobs)",
                        frequency=int(retry_rate),
                        evidence=[]
                    )
                    if result == 'created':
                        created += 1
                    elif result == 'updated':
                        updated += 1

        scanned = len(patterns) + len(retry_patterns)
        logger.info(f"HR scan complete: {scanned} patterns found, {created} points created, {updated} updated")
        return {"scanned": scanned, "points_created": created, "points_updated": updated}

    async def _create_or_update_point(
        self,
        conn,
        agent_role: str,
        issue: str,
        frequency: int,
        evidence: List[str]
    ) -> str:
        """Create or update a development point. Returns 'created', 'updated', or 'unchanged'."""

        # Check if a similar point already exists
        existing = await conn.fetchrow("""
            SELECT point_id, frequency
            FROM development_points
            WHERE agent_role = $1
              AND issue_description = $2
              AND status NOT IN ('RESOLVED', 'DISMISSED')
        """, agent_role, issue)

        if existing:
            if frequency > existing['frequency']:
                await conn.execute("""
                    UPDATE development_points
                    SET frequency = $1, updated_at = NOW()
                    WHERE point_id = $2
                """, frequency, existing['point_id'])
                return 'updated'
            return 'unchanged'

        # Create new point
        point_id = f"DP-{datetime.now().strftime('%Y%m%d')}-{agent_role[:3].upper()}-{frequency:03d}"

        # Ensure uniqueness by adding a counter suffix if needed
        existing_point = await conn.fetchrow(
            "SELECT 1 FROM development_points WHERE point_id = $1", point_id
        )
        if existing_point:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM development_points WHERE point_id LIKE $1",
                f"{point_id}%"
            )
            point_id = f"{point_id}-{count + 1}"

        impact = self._calculate_impact(frequency)

        await conn.execute("""
            INSERT INTO development_points (
                point_id, agent_role, issue_description,
                frequency, impact, evidence_example, status,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, 'OPEN', NOW(), NOW())
        """,
            point_id,
            agent_role,
            issue,
            frequency,
            impact,
            json.dumps(evidence)
        )
        return 'created'

    def _calculate_impact(self, frequency: int) -> str:
        """Calculate impact based on frequency."""
        if frequency >= 10:
            return "HIGH"
        elif frequency >= 5:
            return "MEDIUM"
        else:
            return "LOW"

    async def generate_weekly_report(self) -> Dict[str, Any]:
        """Generate weekly performance report per agent."""
        if not self.db_pool:
            return {}

        report = {}

        async with self.db_pool.acquire() as conn:
            # Get all agent roles from recent steps
            agents = await conn.fetch("""
                SELECT DISTINCT agent_role
                FROM job_steps
                WHERE agent_role IS NOT NULL AND agent_role != 'orchestrator'
            """)

            for agent in agents:
                role = agent['agent_role']

                # Open development points
                points = await conn.fetch("""
                    SELECT point_id, issue_description, frequency, impact, created_at
                    FROM development_points
                    WHERE agent_role = $1 AND status = 'OPEN'
                    ORDER BY impact DESC, frequency DESC
                """, role)

                # Performance stats (last 7 days)
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) AS total_steps,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_steps,
                        COUNT(DISTINCT job_id) AS unique_jobs
                    FROM job_steps
                    WHERE agent_role = $1
                      AND created_at > NOW() - INTERVAL '7 days'
                """, role)

                total = stats['total_steps'] or 0
                failed = stats['failed_steps'] or 0
                unique = stats['unique_jobs'] or 0

                # Calculate retry rate: (total - unique) / unique
                retry_rate = (total - unique) / unique if unique > 0 else 0

                report[role] = {
                    "open_points": [
                        {
                            "point_id": p['point_id'],
                            "issue": p['issue_description'],
                            "frequency": p['frequency'],
                            "impact": p['impact'],
                            "created_at": p['created_at'].isoformat() if p['created_at'] else None
                        }
                        for p in points
                    ],
                    "total_steps": total,
                    "failed_steps": failed,
                    "unique_jobs": unique,
                    "retry_rate": round(retry_rate, 2),
                    "success_rate": round((total - failed) / total, 2) if total > 0 else 1.0
                }

        return report

    async def get_development_points(
        self,
        agent_role: str = None,
        impact: str = None,
        status: str = "OPEN"
    ) -> List[Dict]:
        """List development points with optional filters."""
        if not self.db_pool:
            return []

        async with self.db_pool.acquire() as conn:
            query = "SELECT * FROM development_points WHERE status = $1"
            params = [status]
            idx = 2

            if agent_role:
                query += f" AND agent_role = ${idx}"
                params.append(agent_role)
                idx += 1

            if impact:
                query += f" AND impact = ${idx}"
                params.append(impact)
                idx += 1

            query += " ORDER BY impact DESC, frequency DESC"

            rows = await conn.fetch(query, *params)

        return [
            {
                **dict(r),
                "id": str(r['id']),
                "created_at": r['created_at'].isoformat() if r.get('created_at') else None,
                "updated_at": r['updated_at'].isoformat() if r.get('updated_at') else None,
                "resolved_at": r['resolved_at'].isoformat() if r.get('resolved_at') else None,
            }
            for r in rows
        ]

    async def resolve_point(self, point_id: str, resolution: str) -> bool:
        """Mark a development point as resolved."""
        if not self.db_pool:
            return False

        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE development_points
                SET status = 'RESOLVED',
                    resolved_at = NOW(),
                    resolution = $1,
                    updated_at = NOW()
                WHERE point_id = $2
            """, resolution, point_id)

        return result != "UPDATE 0"

    async def dismiss_point(self, point_id: str) -> bool:
        """Dismiss a development point."""
        if not self.db_pool:
            return False

        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE development_points
                SET status = 'DISMISSED', updated_at = NOW()
                WHERE point_id = $1
            """, point_id)

        return result != "UPDATE 0"
