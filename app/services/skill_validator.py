"""
A/B validation for skill effectiveness.
"""
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class SkillValidator:
    """Measures skill effectiveness via A/B comparison."""

    def __init__(self, pool):
        self.pool = pool

    async def calculate_skill_effectiveness(self, skill_id: str, days: int = 30) -> Dict:
        """
        Calculates how much a skill improves job success.

        Compares:
        - Jobs where skill was used
        - Jobs where skill was NOT used (baseline)
        """
        async with self.pool.acquire() as conn:
            with_skill = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN job_success THEN 1 ELSE 0 END), 0) as successes,
                    COALESCE(AVG(retry_count), 0) as avg_retries,
                    COALESCE(AVG(execution_time_ms), 0) as avg_time
                FROM skill_usage_log
                WHERE skill_id = $1
                  AND logged_at > NOW() - ($2 * INTERVAL '1 day')
                """,
                skill_id,
                days,
            )

            baseline = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT j.id) as total,
                    COALESCE(SUM(CASE WHEN j.status IN ('JOB_READY', 'COMPLETED') THEN 1 ELSE 0 END), 0) as successes,
                    COALESCE(AVG(js.retry_count), 0) as avg_retries
                FROM jobs j
                LEFT JOIN job_steps js ON j.id = js.job_id
                WHERE j.created_at > NOW() - ($2 * INTERVAL '1 day')
                  AND j.id NOT IN (
                    SELECT DISTINCT job_id FROM skill_usage_log WHERE skill_id = $1
                  )
                """,
                skill_id,
                days,
            )

        with_data = dict(with_skill or {})
        base_data = dict(baseline or {})

        with_total = with_data.get("total") or 0
        base_total = base_data.get("total") or 0

        with_success_rate = (with_data.get("successes", 0) / with_total) if with_total > 0 else 0
        base_success_rate = (base_data.get("successes", 0) / base_total) if base_total > 0 else 0
        improvement = with_success_rate - base_success_rate

        return {
            "skill_id": skill_id,
            "with_skill": {
                "jobs": with_total,
                "success_rate": round(with_success_rate, 3),
                "avg_retries": round(float(with_data.get("avg_retries", 0)), 2),
                "avg_time_ms": int(with_data.get("avg_time", 0) or 0),
            },
            "baseline": {
                "jobs": base_total,
                "success_rate": round(base_success_rate, 3),
                "avg_retries": round(float(base_data.get("avg_retries", 0)), 2),
            },
            "improvement": round(improvement, 3),
            "effective": improvement > 0.05,
            "confidence": self._calculate_confidence(with_total, base_total),
        }

    def _calculate_confidence(self, with_n: int, base_n: int) -> str:
        total = with_n + base_n
        if total < 10:
            return "low"
        if total < 30:
            return "medium"
        return "high"

    async def get_all_skill_effectiveness(self, days: int = 30) -> List[Dict]:
        async with self.pool.acquire() as conn:
            skills = await conn.fetch("SELECT skill_id FROM agent_skills")

        results: List[Dict] = []
        for skill in skills:
            effectiveness = await self.calculate_skill_effectiveness(skill["skill_id"], days)
            results.append(effectiveness)

        results.sort(key=lambda x: x["improvement"], reverse=True)
        return results
