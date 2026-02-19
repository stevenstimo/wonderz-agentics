"""Token Guard — enforces per-job token budgets.

Prevents runaway LLM costs by tracking token usage and hard-stopping
jobs that exceed their budget.
"""
import os
import logging
import asyncpg
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://wonderz:wonderz123@localhost:5432/wonderz")


class TokenGuard:
    """Enforces token budgets for jobs."""

    WARNING_THRESHOLD = 0.80  # 80% = warning

    def __init__(self, db_pool=None):
        self.db_pool = db_pool

    async def _get_conn(self):
        """Get a connection from pool or create a direct one."""
        if self.db_pool:
            return self.db_pool.acquire()
        # Fallback: direct connection (works in Celery worker)
        return _DirectConn(DATABASE_URL)

    async def check_before_call(
        self,
        job_id: str,
        estimated_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """Check whether an LLM call is within budget.

        Returns dict with at minimum ``{"allowed": bool}``.
        When *not* allowed the dict also contains ``reason``, ``used``, ``budget``.
        When nearing the limit it contains ``warning: True`` and ``percentage``.
        """
        try:
            async with await self._get_conn() as conn:
                job = await conn.fetchrow(
                    "SELECT token_budget, tokens_used FROM jobs WHERE id = $1",
                    job_id,
                )

                if not job:
                    return {"allowed": False, "reason": "job_not_found"}

                budget = job["token_budget"] or 50_000
                used = job["tokens_used"] or 0
                projected = used + estimated_tokens

                if projected >= budget:
                    # Hard stop
                    await conn.execute(
                        "UPDATE jobs SET status = 'FAILED', token_limit_exceeded_at = NOW() WHERE id = $1",
                        job_id,
                    )
                    logger.warning(
                        "Token budget exceeded for job %s: %d/%d",
                        job_id, used, budget,
                    )
                    return {
                        "allowed": False,
                        "reason": "token_budget_exceeded",
                        "used": used,
                        "budget": budget,
                    }

                if budget > 0 and projected / budget >= self.WARNING_THRESHOLD:
                    pct = (projected / budget) * 100
                    logger.info(
                        "Token budget warning for job %s: %.1f%% used",
                        job_id, pct,
                    )
                    return {
                        "allowed": True,
                        "warning": True,
                        "used": used,
                        "budget": budget,
                        "percentage": pct,
                    }

                return {"allowed": True, "used": used, "budget": budget}
        except Exception as e:
            logger.error("TokenGuard check failed for job %s: %s", job_id, e)
            return {"allowed": True}  # fail-open on DB errors

    async def register_usage(
        self,
        job_id: str,
        tokens_used: int,
        step_id: Optional[str] = None,
    ):
        """Record actual token usage after an LLM call."""
        if tokens_used <= 0:
            return

        try:
            async with await self._get_conn() as conn:
                await conn.execute(
                    "UPDATE jobs SET tokens_used = COALESCE(tokens_used, 0) + $1 WHERE id = $2",
                    tokens_used, job_id,
                )
                if step_id:
                    await conn.execute(
                        "UPDATE job_steps SET tokens_used = COALESCE(tokens_used, 0) + $1 WHERE id = $2",
                        tokens_used, step_id,
                    )
        except Exception as e:
            logger.error("TokenGuard register_usage failed for job %s: %s", job_id, e)


class _DirectConn:
    """Context manager that creates and closes a direct asyncpg connection."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn = None

    async def __aenter__(self):
        self.conn = await asyncpg.connect(self.dsn)
        return self.conn

    async def __aexit__(self, *args):
        if self.conn:
            await self.conn.close()
