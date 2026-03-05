import json
import os
import asyncpg
import logging
from typing import Optional
import subprocess
import sys

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
_pool: Optional[asyncpg.pool.Pool] = None


def _normalized_database_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def run_migrations():
    """Run pending database migrations."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.migrations.runner"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "DATABASE_URL": DATABASE_URL}
        )
        if result.returncode == 0:
            logger.info("✓ Database migrations completed")
        else:
            logger.error(f"Migration failed: {result.stderr}")
            raise RuntimeError("Database migrations failed")
    except Exception as e:
        logger.warning(f"Could not run migrations: {e}")
        # Non-fatal - proceed without migrations


async def _init_connection_codecs(conn: asyncpg.Connection) -> None:
    """Register jsonb codec so Python dicts/list are serialized automatically."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_db_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not configured - database features will be unavailable")
            return None
        
        try:
            # Run migrations first
            if os.getenv("RUN_MIGRATIONS", "true").lower() == "true":
                await run_migrations()
            
            db_url = _normalized_database_url(DATABASE_URL)
            _pool = await asyncpg.create_pool(db_url, init=_init_connection_codecs)
            logger.info("✓ Database connection pool created")
        except Exception as e:
            logger.warning(f"Failed to initialize database pool: {e}")
            logger.warning("Continuing without database - some features may be unavailable")
            return None
    return _pool


async def close_db_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def acquire_connection():
    pool = await init_db_pool()
    return await pool.acquire()


async def release_connection(conn):
    pool = _pool
    if pool and conn:
        await pool.release(conn)
