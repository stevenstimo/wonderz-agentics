# Pattern: fire-and-forget / Aanpak A
"""
Mark long-running fire-and-forget work as failed after a timeout.

Runs on API and ARQ worker startup. Does not touch NEXUS `jobs` (see recover_stuck_jobs in main).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_STUCK_MINUTES = int(os.getenv("FIRE_AND_FORGET_STUCK_MINUTES", "120"))

_MSG = (
    "Verwerking onderbroken (worker/backend herstart of time-out). "
    "Start de actie opnieuw indien nodig."
)


async def _seo_jobs_has_updated_at(conn) -> bool:
    row = await conn.fetchval(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'seo_jobs'
          AND column_name = 'updated_at'
        """
    )
    return row is not None


async def recover_stuck_fire_and_forget_work(pool) -> None:
    """Reset rows stuck in `processing` / embedding processing for too long."""
    if not pool:
        return
    m = _STUCK_MINUTES
    kd = ds = seo = "SKIP"

    async def _run_kd() -> str:
        async with pool.acquire() as conn:
            return await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE embedding_status = 'processing'
                  AND updated_at < now() - ($1::bigint * interval '1 minute')
                """,
                m,
            )

    async def _run_ds() -> str:
        async with pool.acquire() as conn:
            return await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'failed',
                    error_detail = $2,
                    updated_at = now()
                WHERE status = 'processing'
                  AND updated_at < now() - ($1::bigint * interval '1 minute')
                """,
                m,
                _MSG,
            )

    async def _run_seo() -> str:
        async with pool.acquire() as conn:
            if await _seo_jobs_has_updated_at(conn):
                return await conn.execute(
                    """
                    UPDATE seo_jobs
                    SET status = 'failed',
                        error_log = COALESCE(error_log, '') || E'\\n' || $2,
                        completed_at = now(),
                        updated_at = now()
                    WHERE status = 'processing'
                      AND updated_at < now() - ($1::bigint * interval '1 minute')
                    """,
                    m,
                    _MSG,
                )
            logger.warning(
                "seo_jobs.updated_at ontbreekt — run app/migrations/084_fire_and_forget_recovery.sql; "
                "SEO stuck recovery gebruikt created_at als fallback."
            )
            return await conn.execute(
                """
                UPDATE seo_jobs
                SET status = 'failed',
                    error_log = COALESCE(error_log, '') || E'\\n' || $2,
                    completed_at = now()
                WHERE status = 'processing'
                  AND created_at < now() - ($1::bigint * interval '1 minute')
                """,
                m,
                _MSG,
            )

    try:
        kd = await _run_kd()
    except Exception:
        logger.exception("Fire-and-forget recovery: knowledge_documents failed")

    try:
        ds = await _run_ds()
    except Exception:
        logger.exception("Fire-and-forget recovery: client_datasources failed")

    try:
        seo = await _run_seo()
    except Exception:
        logger.exception("Fire-and-forget recovery: seo_jobs failed")

    logger.info(
        "Fire-and-forget recovery: knowledge_documents=%s client_datasources=%s seo_jobs=%s (%s min)",
        kd,
        ds,
        seo,
        m,
    )
