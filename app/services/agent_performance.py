"""
Agent performance tracking.
Updated after each completed job step in the NEXUS pipeline (hired_agents).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def record_step_completion(
    pool: Any,
    agent_id: str,
    success: bool = True,
) -> None:
    """
    Record a finished job step for an agent in hired_agents.

    On success:
    - completed_tasks + 1
    - performance_score = LEAST(100, completed_tasks * 10)

    On failure:
    - completed_tasks unchanged (no failed_tasks column in base schema)
    - performance_score recalculated from current completed_tasks (unchanged numerically)

    Fail-open: on DB errors log a warning and do not raise.
    """
    if not pool or not agent_id or not str(agent_id).strip():
        return

    agent_id = str(agent_id).strip()

    try:
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM hired_agents WHERE agent_id = $1",
                agent_id,
            )
            if not exists:
                logger.warning(
                    "[PERF] agent_id not found in hired_agents: %s",
                    agent_id,
                )
                return

            if success:
                await conn.execute(
                    """
                    UPDATE hired_agents
                    SET completed_tasks = COALESCE(completed_tasks, 0) + 1,
                        updated_at = now()
                    WHERE agent_id = $1
                    """,
                    agent_id,
                )

            await conn.execute(
                """
                UPDATE hired_agents
                SET performance_score = LEAST(100, COALESCE(completed_tasks, 0) * 10),
                    updated_at = now()
                WHERE agent_id = $1
                """,
                agent_id,
            )

            new_score = await conn.fetchval(
                "SELECT performance_score FROM hired_agents WHERE agent_id = $1",
                agent_id,
            )
            logger.info(
                "[PERF] %s success=%s performance_score=%s",
                agent_id,
                success,
                new_score,
            )

    except Exception as e:
        logger.warning(
            "[PERF] Failed to update performance for %s: %s",
            agent_id,
            e,
            exc_info=True,
        )
