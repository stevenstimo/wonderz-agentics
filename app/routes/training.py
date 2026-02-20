from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from app.db import init_db_pool
from app.services.training import train_agent_from_url, TrainingError

router = APIRouter(prefix="/api/training", tags=["training"])


class TrainingRequest(BaseModel):
    agent_id: str
    source_url: HttpUrl
    approved_by: str = "user"


@router.post("/start")
async def start_training(req: TrainingRequest):
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
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
