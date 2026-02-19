"""SkillLoader — loads and manages agent skills for pre-task injection."""
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SkillLoader:
    """Loads and manages agent skills."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def get_agent_skills(self, agent_id: str) -> List[Dict]:
        """Haal alle skills op die aan een agent zijn toegewezen."""
        if not self.db_pool:
            logger.warning("No DB pool available - skills disabled")
            return []

        try:
            async with self.db_pool.acquire() as conn:
                skills = await conn.fetch("""
                    SELECT
                        s.skill_id,
                        s.name,
                        s.domain,
                        s.skill_type,
                        s.content,
                        s.success_rate,
                        s.applicable_to,
                        a.proficiency
                    FROM agent_skills s
                    JOIN agent_skill_assignments a ON s.skill_id = a.skill_id
                    WHERE a.agent_id = $1
                    ORDER BY s.success_rate DESC, s.usage_count DESC
                """, agent_id)

            return [dict(s) for s in skills]
        except Exception as exc:
            logger.error("Failed to load skills for agent %s: %s", agent_id, exc)
            return []

    async def get_skills_by_domain(
        self,
        domain: str,
        limit: int = 10,
    ) -> List[Dict]:
        """Haal top skills voor een domein op."""
        if not self.db_pool:
            return []

        try:
            async with self.db_pool.acquire() as conn:
                skills = await conn.fetch("""
                    SELECT * FROM agent_skills
                    WHERE domain = $1 OR $1 = ANY(applicable_to)
                    ORDER BY success_rate DESC, usage_count DESC
                    LIMIT $2
                """, domain, limit)

            return [dict(s) for s in skills]
        except Exception as exc:
            logger.error("Failed to load skills for domain %s: %s", domain, exc)
            return []

    async def get_skills_by_type(
        self,
        skill_type: str,
        applicable_to: Optional[str] = None,
    ) -> List[Dict]:
        """Haal skills op basis van type (bijv. 'voice', 'technique')."""
        if not self.db_pool:
            return []

        try:
            async with self.db_pool.acquire() as conn:
                if applicable_to:
                    skills = await conn.fetch("""
                        SELECT * FROM agent_skills
                        WHERE skill_type = $1
                          AND $2 = ANY(applicable_to)
                        ORDER BY success_rate DESC
                    """, skill_type, applicable_to)
                else:
                    skills = await conn.fetch("""
                        SELECT * FROM agent_skills
                        WHERE skill_type = $1
                        ORDER BY success_rate DESC
                    """, skill_type)

            return [dict(s) for s in skills]
        except Exception as exc:
            logger.error("Failed to load skills for type %s: %s", skill_type, exc)
            return []

    async def record_skill_usage(
        self,
        job_id: str,
        agent_id: str,
        skill_ids: List[str],
    ):
        """Track welke skills gebruikt zijn voor een job."""
        if not self.db_pool or not skill_ids:
            return

        try:
            async with self.db_pool.acquire() as conn:
                for skill_id in skill_ids:
                    await conn.execute("""
                        UPDATE agent_skills
                        SET usage_count = usage_count + 1,
                            updated_at = NOW()
                        WHERE skill_id = $1
                    """, skill_id)

                    await conn.execute("""
                        INSERT INTO skill_usage_log (job_id, agent_id, skill_id, was_successful, logged_at)
                        VALUES ($1, $2, $3, NULL, NOW())
                    """, job_id, agent_id, skill_id)

            logger.info("Tracked %s skills for job %s", len(skill_ids), job_id)
        except Exception as exc:
            logger.error("Failed to track skill usage: %s", exc)

    async def update_skill_success(
        self,
        skill_id: str,
        was_successful: bool,
        feedback: Optional[str] = None,
    ):
        """Update success rate na job completion (exponential moving average)."""
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE agent_skills
                    SET success_rate = (
                        success_rate * 0.9 +
                        CASE WHEN $2 THEN 1.0 ELSE 0.0 END * 0.1
                    ),
                    updated_at = NOW()
                    WHERE skill_id = $1
                """, skill_id, was_successful)

                await conn.execute("""
                    UPDATE skill_usage_log
                    SET was_successful = $2, feedback = $3
                    WHERE skill_id = $1
                      AND was_successful IS NULL
                    ORDER BY logged_at DESC
                    LIMIT 1
                """, skill_id, was_successful, feedback)

            logger.info("Updated skill %s success: %s", skill_id, was_successful)
        except Exception as exc:
            logger.error("Failed to update skill success: %s", exc)

    def compose_skill_context(self, skills: List[Dict]) -> str:
        """Compose skills naar één context string voor de system prompt."""
        if not skills:
            return ""

        sections = []
        for skill in skills:
            proficiency = skill.get("proficiency", "competent")
            success_rate = skill.get("success_rate", 0.5) * 100
            sections.append(
                f"## Skill: {skill['name']} ({skill['skill_type']})\n"
                f"**Your proficiency:** {proficiency}\n"
                f"**Success rate:** {success_rate:.0f}%\n\n"
                f"{skill['content']}"
            )

        return "\n\n---\n\n".join(sections)

    def determine_applicable_skills(
        self,
        agent_skills: List[Dict],
        task_context: Dict,
    ) -> List[Dict]:
        """Bepaal welke skills relevant zijn voor deze specifieke taak."""
        applicable = []

        job_post = task_context.get("job_post", "").lower()
        platform = task_context.get("platform", "").lower()
        target_audience = task_context.get("target_audience", "").lower()

        for skill in agent_skills:
            skill_id = skill["skill_id"]

            if "seo" in skill_id:
                if "website" in platform or "blog" in platform or "web" in platform:
                    applicable.append(skill)
                    continue

            if "b2b-professional" in skill_id:
                if any(kw in target_audience for kw in ["b2b", "professional", "business", "corporate"]):
                    applicable.append(skill)
                    continue

            if "casual" in skill_id:
                if any(kw in target_audience for kw in ["casual", "consumer", "jeugd", "jong", "tiener"]):
                    applicable.append(skill)
                    continue

            if "structure" in skill_id or "hierarchy" in skill_id:
                applicable.append(skill)
                continue

            if "anti-pattern" in skill_id:
                applicable.append(skill)
                continue

        logger.info("Selected %s/%s skills for task", len(applicable), len(agent_skills))
        return applicable
