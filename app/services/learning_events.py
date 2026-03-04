"""
Cross-agent learning system.
"""
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class LearningEventManager:
    """Manages knowledge sharing between agents."""

    def __init__(self, pool):
        self.pool = pool

    async def detect_learning_event(self, agent_id: str, skill_id: str, improvement: float) -> bool:
        """
        Detect if a learning event is worth sharing.

        Criteria:
        - Improvement > 10%
        - Skill used > 5 times
        - Success rate > 0.7
        """
        if improvement < 0.10:
            return False

        async with self.pool.acquire() as conn:
            usage = await conn.fetchrow(
                """
                SELECT COUNT(*) as uses,
                       COALESCE(AVG(CASE WHEN job_success THEN 1 ELSE 0 END), 0) as success_rate
                FROM skill_usage_log
                WHERE agent_id = $1 AND skill_id = $2
                """,
                agent_id,
                skill_id,
            )

        if not usage:
            return False

        if (usage["uses"] or 0) < 5:
            return False

        if (usage["success_rate"] or 0) < 0.7:
            return False

        return True

    async def propagate_skill(self, source_agent_id: str, skill_id: str, target_role: str) -> int:
        """
        Propagate successful skill to other agents with same role.

        Returns: number of agents that received the skill.
        """
        async with self.pool.acquire() as conn:
            candidates = await conn.fetch(
                """
                SELECT agent_id
                FROM hired_agents
                WHERE role = $1
                  AND agent_id != $2
                  AND status = 'active'
                  AND agent_id NOT IN (
                    SELECT agent_id
                    FROM agent_skill_assignments
                    WHERE skill_id = $3
                  )
                """,
                target_role,
                source_agent_id,
                skill_id,
            )

            propagated = 0
            for candidate in candidates:
                await conn.execute(
                    """
                    INSERT INTO agent_skill_assignments (agent_id, skill_id, proficiency)
                    VALUES ($1, $2, 'intermediate')
                    ON CONFLICT DO NOTHING
                    """,
                    candidate["agent_id"],
                    skill_id,
                )
                propagated += 1
                logger.info(
                    "Propagated skill %s from %s to %s",
                    skill_id,
                    source_agent_id,
                    candidate["agent_id"],
                )

            await conn.execute(
                """
                INSERT INTO learning_events (
                    source_agent_id,
                    skill_id,
                    target_role,
                    propagated_to,
                    created_at
                ) VALUES ($1, $2, $3, $4, NOW())
                """,
                source_agent_id,
                skill_id,
                target_role,
                propagated,
            )

        return propagated
