import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl, root_validator
from app.db import init_db_pool
from app.services.training import train_agent_from_url, TrainingError

router = APIRouter(prefix="/api/training", tags=["training"])
logger = logging.getLogger(__name__)


async def _get_table_columns(conn, table_name: str) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table_name,
    )
    return {row["column_name"] for row in rows}


class TrainingRequest(BaseModel):
    agent_id: str
    source_url: HttpUrl | None = None
    url: HttpUrl | None = None
    title: str | None = None
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


@router.get("/sessions")
async def list_training_sessions():
    """List all training sessions (knowledge ingestion history)."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT agent_id, source_url, chunk_index, created_at
               FROM agent_knowledge
               WHERE is_active = true
               ORDER BY created_at DESC LIMIT 100"""
        )
        # Group by agent + source
        sessions = {}
        for r in rows:
            key = f"{r['agent_id']}:{r['source_url']}"
            if key not in sessions:
                sessions[key] = {
                    "agent_id": r["agent_id"],
                    "source_url": r["source_url"],
                    "chunks": 0,
                    "created_at": str(r["created_at"]),
                    "status": "completed",
                }
            sessions[key]["chunks"] += 1
    return list(sessions.values())


@router.get("/{agent_id}/knowledge-base")
async def get_knowledge_base(agent_id: str):
    """Get knowledge base chunks for an agent."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with pool.acquire() as conn:
        columns = await _get_table_columns(conn, "agent_knowledge")
        id_column = "id" if "id" in columns else "knowledge_id" if "knowledge_id" in columns else None
        if not id_column:
            raise HTTPException(status_code=500, detail="agent_knowledge id column not found")
        rows = await conn.fetch(
            f"""SELECT {id_column} as id, source_url, chunk_text, chunk_index, created_at
               FROM agent_knowledge
               WHERE agent_id = $1 AND is_active = true
               ORDER BY created_at DESC LIMIT 50""",
            agent_id,
        )
    return [{"id": str(r["id"]), "source_url": r["source_url"],
             "text": r["chunk_text"][:200], "chunk_index": r["chunk_index"],
             "created_at": str(r["created_at"])} for r in rows]


@router.post("/request")
async def request_training(req: TrainingRequest):
    """Alias for /start — used by TrainingManagement frontend."""
    return await start_training(req)


@router.post("/{session_id}/complete")
async def complete_training(session_id: str):
    """Mark a training session as complete (no-op, sessions auto-complete)."""
    return {"session_id": session_id, "status": "completed"}


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
        columns = await _get_table_columns(conn, "hired_agents")
        sources_column = "knowledge_base_sources" if "knowledge_base_sources" in columns else "knowledge_sources" if "knowledge_sources" in columns else None
        if not sources_column:
            raise HTTPException(status_code=500, detail="Knowledge sources column not found")

        agent = await conn.fetchrow(
            f"SELECT {sources_column} FROM hired_agents WHERE agent_id = $1",
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

    sources = json.loads(agent[sources_column]) if agent[sources_column] else []

    return {
        "agent_id": agent_id,
        "total_chunks": chunk_count,
        "sources": sources,
    }
