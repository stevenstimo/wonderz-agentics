import os
import asyncpg
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL")
_pool: Optional[asyncpg.pool.Pool] = None


async def init_db_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        _pool = await asyncpg.create_pool(DATABASE_URL)
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
