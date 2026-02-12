import os
import asyncpg
import logging
from typing import Optional
import subprocess
import sys

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
_pool: Optional[asyncpg.pool.Pool] = None


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
            
            _pool = await asyncpg.create_pool(DATABASE_URL)
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
