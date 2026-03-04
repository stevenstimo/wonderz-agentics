import asyncpg
from fastapi import HTTPException

from app.db import init_db_pool


async def get_db() -> asyncpg.pool.Pool:
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")
    return pool
