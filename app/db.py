"""Async PostgreSQL connection pool (asyncpg). Used by app.database.get_db()."""
import os
import logging
import asyncpg

logger = logging.getLogger(__name__)
_pool: asyncpg.Pool | None = None


async def init_db_pool() -> asyncpg.Pool | None:
    """Create or return the global asyncpg pool. Reads DATABASE_URL at runtime."""
    global _pool
    if _pool is not None:
        return _pool
    dsn = os.getenv("DATABASE_URL", "postgresql://wonderz:wonderz123@localhost:5432/wonderz")
    try:
        # Strip pgbouncer query param (not a libpq param, confuses asyncpg)
        if "pgbouncer=true" in dsn:
            dsn = dsn.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
        _pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=10,
            command_timeout=60,
            # Disable prepared‑statement cache for PgBouncer/Supavisor compat
            statement_cache_size=0,
        )
        logger.info("Database pool initialised")
        return _pool
    except Exception as e:
        logger.exception("Failed to create database pool: %s", e)
        return None


async def close_db_pool() -> None:
    """Close the global pool (e.g. on app shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")
