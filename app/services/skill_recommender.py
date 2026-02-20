"""
Skill recommendation engine.
"""
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class SkillRecommender:
    """Analyzes agent failures and recommends relevant skills."""

    def __init__(self, pool):
        self.pool = pool
        self._columns_cache: Dict[str, set] = {}

        # Skill -> Training URL mapping
        self.skill_resources = {
            "seo-copywriting": [
                "https://www.shopify.com/blog/ecommerce-seo",
                "https://ahrefs.com/blog/ecommerce-seo/",
            ],
            "content-structure": [
                "https://contentmarketinginstitute.com/articles/content-structure/",
            ],
            "b2b-voice": [
                "https://www.copyblogger.com/b2b-copywriting/",
            ],
        }

    async def _get_table_columns(self, conn, table_name: str) -> set:
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

    async def get_recommendations_for_agent(self, agent_id: str, limit: int = 5) -> List[Dict]:
        """
        Get skill recommendations based on agent's failure patterns.
        """
        async with self.pool.acquire() as conn:
            step_cols = await self._get_table_columns(conn, "job_steps")
            job_cols = await self._get_table_columns(conn, "jobs")

            agent_col = "agent_id" if "agent_id" in step_cols else "agent_role" if "agent_role" in step_cols else None
            time_col = "started_at" if "started_at" in step_cols else "created_at" if "created_at" in step_cols else None

            if not agent_col or not time_col:
                logger.warning("Recommendation scan skipped: job_steps missing agent/time columns")
                return []

            agent_role = None
            if agent_col == "agent_role":
                agent_role = await conn.fetchval(
                    "SELECT role FROM hired_agents WHERE agent_id = $1",
                    agent_id,
                )
                if not agent_role:
                    logger.warning("No role found for agent %s", agent_id)
                    return []

            failures = await conn.fetch(
                """
                SELECT
                    js.feedback as retry_reason,
                    COUNT(*) as frequency,
                    j.context->>'platform' as platform,
                    j.context->>'audience' as audience
                FROM job_steps js
                JOIN jobs j ON j.id::text = js.job_id::text
                WHERE js.agent_role = $1
                  AND js.status = 'failed'
                  AND js.started_at > NOW() - INTERVAL '30 days'
                GROUP BY js.feedback, platform, audience
                ORDER BY COUNT(*) DESC
                LIMIT 10
                """,
                agent_id,
            )

            existing_skills = await conn.fetch(
                """
                SELECT skill_id
                FROM agent_skill_assignments
                WHERE agent_id = $1
                """,
                agent_id,
            )
            existing_ids = {s["skill_id"] for s in existing_skills}

            all_skills = await conn.fetch("SELECT * FROM agent_skills")

        recommendations: List[Dict] = []

        for skill in all_skills:
            skill_dict = dict(skill)
            skill_id = skill_dict.get("skill_id")
            if not skill_id or skill_id in existing_ids:
                continue

            score = self._calculate_relevance_score(skill_dict, failures)
            if score > 0.3:
                recommendations.append({
                    "skill_id": skill_id,
                    "skill_name": skill_dict.get("name"),
                    "relevance_score": round(score, 3),
                    "reason": self._generate_reason(failures),
                    "suggested_urls": self.skill_resources.get(skill_id, []),
                    "estimated_improvement": self._estimate_improvement(skill_dict),
                })

        recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)
        return recommendations[:limit]

    def _calculate_relevance_score(self, skill: Dict, failures: List[Dict]) -> float:
        score = 0.0
        skill_tags = skill.get("tags") or []
        if isinstance(skill_tags, str):
            skill_tags = [t.strip() for t in skill_tags.split(",") if t.strip()]

        skill_name = (skill.get("name") or "").lower()
        skill_id = (skill.get("skill_id") or "").lower()

        for failure in failures:
            reason = (failure.get("retry_reason") or "").lower()
            frequency = float(failure.get("frequency") or 0)
            weight = min(frequency / 10.0, 1.0)

            for tag in skill_tags:
                if tag.lower() in reason:
                    score += 0.2 * weight

            if skill_name and skill_name in reason:
                score += 0.1 * weight
            if skill_id and skill_id in reason:
                score += 0.1 * weight

        success_rate = skill.get("success_rate")
        if success_rate is None:
            success_rate = 0.5
        try:
            success_rate = float(success_rate)
        except (TypeError, ValueError):
            success_rate = 0.5

        score *= success_rate
        return min(score, 1.0)

    def _generate_reason(self, failures: List[Dict]) -> str:
        if not failures:
            return "This skill could improve overall performance"
        top_failure = failures[0].get("retry_reason") or "recent failures"
        return f"Could help with: {top_failure} ({failures[0].get('frequency', 0)}x)"

    def _estimate_improvement(self, skill: Dict) -> str:
        rate = skill.get("success_rate")
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            rate = 0.5

        if rate > 0.8:
            return "High potential"
        if rate > 0.6:
            return "Medium potential"
        return "Experimental"
