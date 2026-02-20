import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl, root_validator
from app.db import init_db_pool
from app.services.training import train_agent_from_url, TrainingError

router = APIRouter(prefix="/api/training", tags=["training"])
logger = logging.getLogger(__name__)


class TrainingRequest(BaseModel):
    agent_id: str
    source_url: HttpUrl | None = None
    url: HttpUrl | None = None
    approved_by: str = "user"

    @root_validator(pre=True)
    def _ensure_source_url(cls, values):
        source_url = values.get("source_url")
        url = values.get("url")
        if not source_url and not url:
            raise ValueError("Either source_url or url is required")
        if not source_url and url:
            values["source_url"] = url
        return values


@router.post("/start")
async def start_training(req: TrainingRequest):
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        if req.url and not req.source_url:
            logger.warning("Deprecated field 'url' used for training start; prefer 'source_url'.")
        result = await train_agent_from_url(
            pool=pool,
            agent_id=req.agent_id,
            url=str(req.source_url),
            approved_by=req.approved_by,
        )
        return result
    except TrainingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{agent_id}/status")
async def get_training_status(agent_id: str):
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        agent = await conn.fetchrow(
            "SELECT knowledge_base_sources FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        chunk_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM agent_knowledge
            WHERE agent_id = $1 AND is_active = true
            """,
            agent_id,
        )

    import json

    sources = json.loads(agent["knowledge_base_sources"]) if agent["knowledge_base_sources"] else []

    return {
        "agent_id": agent_id,
        "total_chunks": chunk_count,
        "sources": sources,
    }
