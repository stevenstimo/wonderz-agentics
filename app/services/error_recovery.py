"""
Automatic error recovery and retry logic.
"""
from __future__ import annotations

from typing import Callable, Any, Optional, Set, Dict
import asyncio
import logging

logger = logging.getLogger(__name__)


class ErrorRecovery:
    """
    Handles automatic retry with exponential backoff.
    """

    def __init__(self, pool):
        self.pool = pool

        # Retry configuration
        self.max_retries = 3
        self.base_delay = 2  # seconds
        self.max_delay = 60  # seconds

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

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable[[int, Exception], Any]] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with automatic retry.

        Uses exponential backoff: 2s, 4s, 8s, ...
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                result = await func(*args, **kwargs)

                if attempt > 0:
                    logger.info("Retry succeeded on attempt %s", attempt + 1)

                return result

            except Exception as exc:
                last_error = exc

                if attempt < self.max_retries - 1:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    if on_retry:
                        await self._maybe_await(on_retry(attempt + 1, exc))
                    logger.warning(
                        "Attempt %s failed: %s. Retrying in %ss...",
                        attempt + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "All %s attempts failed. Last error: %s",
                        self.max_retries,
                        exc,
                    )

        raise last_error

    async def graceful_degradation(
        self,
        primary_func: Callable,
        fallback_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Try primary function, fallback to secondary on failure.

        Example:
        - Primary: Use Claude Sonnet
        - Fallback: Use Claude Haiku
        """
        try:
            return await self.execute_with_retry(primary_func, *args, **kwargs)
        except Exception as exc:
            logger.warning("Primary function failed, using fallback: %s", exc)
            return await fallback_func(*args, **kwargs)

    async def record_retry(self, step_id: int, error: str):
        """Record retry metadata on a job step (if columns exist)."""
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            cols = await self._get_table_columns(conn, "job_steps")
            if "id" not in cols or "retry_count" not in cols:
                return

            if "retry_reason" in cols:
                await conn.execute(
                    """
                    UPDATE job_steps
                    SET retry_count = COALESCE(retry_count, 0) + 1,
                        retry_reason = $2
                    WHERE id = $1
                    """,
                    step_id,
                    error,
                )
            else:
                await conn.execute(
                    """
                    UPDATE job_steps
                    SET retry_count = COALESCE(retry_count, 0) + 1
                    WHERE id = $1
                    """,
                    step_id,
                )

    async def mark_job_for_retry(self, job_id: str, error: str):
        """Mark job for manual retry after exhausting auto-retry."""
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'BLOCKED',
                    context = jsonb_set(
                        jsonb_set(
                            COALESCE(context, '{}'::jsonb),
                            '{retry_needed}',
                            'true'::jsonb,
                            true
                        ),
                        '{last_error}',
                        to_jsonb($2::text),
                        true
                    )
                WHERE id = $1
                """,
                job_id,
                error,
            )

            logger.info("Job %s marked for manual retry: %s", job_id, error)

    async def record_dead_letter(
        self,
        job_id: str,
        agent_id: Optional[str],
        error_message: str,
        retry_count: int = 0,
    ):
        """Insert entry into dead letter queue (if available)."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO dead_letter_queue (
                        job_id,
                        agent_id,
                        error_message,
                        retry_count,
                        last_retry_at
                    )
                    VALUES ($1, $2, $3, $4, NOW())
                    """,
                    job_id,
                    agent_id,
                    error_message,
                    retry_count,
                )
        except Exception as exc:
            logger.warning("Failed to record dead letter for job %s: %s", job_id, exc)

    async def _maybe_await(self, value):
        if asyncio.iscoroutine(value):
            return await value
        return value
