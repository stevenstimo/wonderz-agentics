from __future__ import annotations

from fastapi import Request

from arq import ArqRedis


async def get_arq_pool(request: Request) -> ArqRedis:
    """Dependency to access the ARQ pool stored in `app.state.arq_pool`."""

    pool = getattr(request.app.state, "arq_pool", None)
    if not pool:
        # Fail fast: without ARQ pool we can't enqueue background work.
        raise RuntimeError("ARQ pool not initialised")
    return pool

