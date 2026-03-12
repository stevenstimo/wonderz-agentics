"""Platform Spec V5 — Knowledge Graph API: pattern trace, lesson edges, patterns list."""
import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/pattern/{pattern_id}/trace", dependencies=[Depends(get_current_user)])
async def get_pattern_trace(
    pattern_id: str,
    pool=Depends(get_db),
) -> dict[str, Any]:
    """Pattern traceability: welke lessons introduceren dit pattern, via welke tasks, agents."""
    if not pool:
        return {"pattern_id": pattern_id, "pattern_name": "", "traces": []}
    graph = KnowledgeGraph()
    traces = await graph.get_pattern_trace(pool, pattern_id)
    pattern_name = ""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name FROM patterns WHERE pattern_id = $1",
                pattern_id,
            )
            if row:
                pattern_name = row["name"] or ""
    except Exception:
        pass
    return {
        "pattern_id": pattern_id,
        "pattern_name": pattern_name,
        "traces": traces,
    }


@router.get("/lesson/{lesson_id}/edges", dependencies=[Depends(get_current_user)])
async def get_lesson_edges(
    lesson_id: str,
    pool=Depends(get_db),
) -> dict[str, Any]:
    """Alle edges van en naar deze lesson."""
    if not pool:
        return {"from_edges": [], "to_edges": []}
    graph = KnowledgeGraph()
    from_edges = await graph.get_edges_from(pool, lesson_id)
    to_edges = await graph.get_edges_to(pool, lesson_id)
    return {"from_edges": from_edges, "to_edges": to_edges}


@router.get("/patterns", dependencies=[Depends(get_current_user)])
async def list_patterns(
    pool=Depends(get_db),
) -> dict[str, Any]:
    """Alle patterns met lesson_count (aantal LESSON_INTRODUCES edges)."""
    if not pool:
        return {"patterns": []}
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT p.pattern_id, p.name, p.pattern_type, p.tags,
                       COUNT(ge.edge_id)::int AS lesson_count
                FROM patterns p
                LEFT JOIN graph_edges ge
                  ON ge.to_id = p.pattern_id AND ge.edge_type = 'LESSON_INTRODUCES'
                GROUP BY p.pattern_id, p.name, p.pattern_type, p.tags
                ORDER BY p.pattern_id
                """
            )
        except Exception:
            return {"patterns": []}
    patterns = [
        {
            "pattern_id": r["pattern_id"],
            "name": r["name"],
            "pattern_type": r["pattern_type"] or "pattern",
            "tags": list(r["tags"]) if r.get("tags") else [],
            "lesson_count": r["lesson_count"] or 0,
        }
        for r in rows
    ]
    return {"patterns": patterns}
