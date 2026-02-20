"""Multi-agent team coordination."""
from typing import List, Dict, Any, Optional
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class TeamCoordinator:
    """Coordinates multiple agents working on same job."""

    def __init__(self, pool, agent_runner=None):
        self.pool = pool
        self.agent_runner = agent_runner

    async def execute_parallel(
        self,
        job_id: str,
        agents: List[str],
        task: Dict[str, Any],
        coordination_strategy: str = "parallel",
    ) -> Dict[str, Any]:
        """
        Execute task with multiple agents in parallel.

        Each agent works independently, results are merged.
        """
        if not agents:
            raise ValueError("No agents provided for parallel execution")

        logger.info("Starting parallel execution with %s agents", len(agents))

        await self._register_team(job_id, agents, coordination_strategy)
        await self._create_shared_context(job_id, task)

        runner = self.agent_runner or self._resolve_agent_runner(job_id)
        if not runner:
            raise RuntimeError("No agent runner available for team execution")

        tasks = [
            self._execute_agent(job_id, agent_id, task, runner)
            for agent_id in agents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = [
            r for r in results
            if not isinstance(r, Exception)
        ]

        merged = await self._merge_results(job_id, successful)
        return merged

    async def _register_team(self, job_id: str, agents: List[str], strategy: str) -> None:
        team_id = f"team:{job_id}:{len(agents)}"
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_teams (team_id, job_id, agents, coordination_strategy)
                VALUES ($1, $2, $3::jsonb, $4)
                ON CONFLICT (team_id) DO NOTHING
                """,
                team_id,
                job_id,
                json.dumps(agents),
                strategy,
            )

    async def _create_shared_context(self, job_id: str, task: Dict[str, Any]) -> None:
        """Create shared context accessible to all agents."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO shared_job_context (job_id, key, value)
                VALUES ($1, 'task', $2::jsonb)
                ON CONFLICT (job_id, key) DO UPDATE
                SET value = EXCLUDED.value
                """,
                job_id,
                json.dumps(task),
            )

    async def _execute_agent(
        self,
        job_id: str,
        agent_id: str,
        task: Dict[str, Any],
        runner,
    ) -> Dict[str, Any]:
        """Execute single agent in team."""
        try:
            result = await _maybe_await(
                runner(agent_id, {"job_id": job_id, "context": {"task": task}})
            )

            await self._contribute_to_context(
                job_id,
                f"result_{agent_id}",
                result,
                agent_id,
            )

            return result
        except Exception as e:
            logger.error("Agent %s failed: %s", agent_id, e)
            raise

    async def _contribute_to_context(
        self,
        job_id: str,
        key: str,
        value: Dict[str, Any],
        agent_id: str,
    ) -> None:
        """Agent contributes to shared context."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO shared_job_context
                (job_id, key, value, contributed_by)
                VALUES ($1, $2, $3::jsonb, $4)
                ON CONFLICT (job_id, key) DO UPDATE
                SET value = EXCLUDED.value,
                    contributed_by = EXCLUDED.contributed_by
                """,
                job_id,
                key,
                json.dumps(value),
                agent_id,
            )

    async def _merge_results(
        self,
        job_id: str,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge results from multiple agents.

        Strategy: Combine all outputs into a single response.
        """
        if not results:
            raise ValueError("No successful results to merge")

        merged = {
            "outputs": results,
            "agent_count": len(results),
            "combined_output": self._combine_outputs(results),
        }

        await self._contribute_to_context(job_id, "merged_output", merged, "team_coordinator")
        return merged

    def _combine_outputs(self, results: List[Dict[str, Any]]) -> str:
        """Combine outputs into single text."""
        combined = []
        for i, result in enumerate(results, 1):
            combined.append(
                f"=== Agent {i} Output ===\n{result.get('output', '')}\n"
            )

        return "\n".join(combined)

    def _resolve_agent_runner(self, job_id: str):
        try:
            from workers.tasks import _build_agent_runner
            return _build_agent_runner(job_id)
        except Exception as exc:
            logger.warning("Could not resolve agent runner: %s", exc)
            return None


async def _maybe_await(value):
    if asyncio.iscoroutine(value):
        return await value
    return value
