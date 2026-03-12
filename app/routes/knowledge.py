"""Knowledge Centre API — list documents, get by id, delete (books).

Endpoints:
- GET /api/knowledge — list documents (query: doc_type, client_slug, limit)
- GET /api/knowledge/{document_id} — get one document with versions and chunk_count
- DELETE /api/knowledge/{document_id} — permanently delete document (no backup)
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"], dependencies=[Depends(get_current_user)])


def _row_to_doc(row) -> dict:
    """Convert knowledge_documents row to JSON-safe dict."""
    out = {
        "document_id": str(row["document_id"]),
        "source_url": row.get("source_url"),
        "source_type": row.get("source_type") or "url",
        "title": row.get("title"),
        "client_slug": row.get("client_slug"),
        "approved_by": row.get("approved_by"),
        "doc_type": row.get("doc_type"),
        "domain": row.get("domain"),
        "status": row.get("status"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }
    for key in ("summary", "version", "owner"):
        if row.get(key) is not None:
            out[key] = row[key]
    return out


@router.get("")
async def list_knowledge(
    doc_type: str | None = Query(None, description="Filter by doc_type"),
    client_slug: str | None = Query(None, description="Filter by client_slug"),
    limit: int = Query(200, ge=1, le=500),
    current_user: TokenPayload = Depends(get_current_user),
):
    """List knowledge documents. Optional filters: doc_type, client_slug."""
    pool = await get_db()
    async with pool.acquire() as conn:
        conditions = []
        params = []
        if doc_type:
            conditions.append("doc_type = $%d" % (len(params) + 1))
            params.append(doc_type)
        if client_slug:
            conditions.append("client_slug = $%d" % (len(params) + 1))
            params.append(client_slug)
        where = (" AND " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        limit_param = len(params)
        q = f"""
            SELECT document_id, source_url, source_type, title, client_slug, approved_by,
                   doc_type, domain, status, summary, version, owner, created_at, updated_at
            FROM knowledge_documents
            WHERE 1=1 {where}
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT ${limit_param}
        """
        rows = await conn.fetch(q, *params)
    return [_row_to_doc(r) for r in rows]


@router.get("/{document_id}")
async def get_knowledge(
    document_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get one knowledge document with versions and chunk count."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT document_id, source_url, source_type, title, client_slug, approved_by,
                   doc_type, domain, status, summary, version, owner, created_at, updated_at
            FROM knowledge_documents
            WHERE document_id = $1
            """,
            document_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        versions = await conn.fetch(
            """
            SELECT version_id, version, change_note, approved_by, snapshot, created_at, created_by
            FROM knowledge_versions
            WHERE document_id = $1
            ORDER BY version DESC
            """,
            document_id,
        )
        chunk_count = await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = $1",
            document_id,
        )
    doc = _row_to_doc(row)
    doc["versions"] = [
        {
            "version_id": str(v["version_id"]),
            "version": v["version"],
            "change_note": v.get("change_note"),
            "approved_by": v.get("approved_by"),
            "created_at": v["created_at"].isoformat() if v.get("created_at") else None,
            "created_by": v.get("created_by"),
        }
        for v in versions
    ]
    doc["chunk_count"] = chunk_count or 0
    return doc


@router.delete("/{document_id}", status_code=204)
async def delete_knowledge(
    document_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Permanently delete a knowledge document. No backup. Cascades to chunks and versions."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT document_id FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        await conn.execute(
            "DELETE FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
    logger.info("Knowledge document deleted: document_id=%s by user=%s", document_id, current_user.user_id)
    return None
