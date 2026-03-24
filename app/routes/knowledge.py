"""Knowledge Centre API — upload, list, get, update, approve, archive, reindex, replace, delete.

Endpoints:
- POST /api/knowledge/upload — file upload (multipart)
- POST /api/knowledge/upload/url — URL ingest (JSON body)
- GET /api/knowledge — list documents (query: doc_type, client_slug, limit)
- GET /api/knowledge/{document_id} — get one document with versions and chunk_count
- PATCH /api/knowledge/{document_id} — update metadata (optional source_url → reindex)
- POST /api/knowledge/{document_id}/approve — approve draft/stale
- POST /api/knowledge/{document_id}/archive — archive document
- POST /api/knowledge/{document_id}/reindex — re-fetch URL, re-chunk (URL-sourced only)
- POST /api/knowledge/{document_id}/replace-content — replace content from file
- DELETE /api/knowledge/{document_id} — permanently delete document (no backup)
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user
from app.dependencies import get_arq_pool
from arq import ArqRedis
from app.services.knowledge_upload_service import DOC_TYPES, insert_pending_document_row

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"], dependencies=[Depends(get_current_user)])


class UploadUrlBody(BaseModel):
    """Body voor URL ingest."""

    url: HttpUrl
    title: Optional[str] = None
    doc_type: str = Field(
        default="sop",
        description="playbook|sop|framework|template|case_study|policy|research|client_context|skill_spec",
    )
    domain: str = Field(..., description="growth|gtm|sales|delivery|ai_systems|core")
    function_tag: str = Field(default="general")
    client_slug: Optional[str] = None
    access_level: str = Field(default="reference")
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None


class ApproveBody(BaseModel):
    change_note: Optional[str] = "approved"
    second_approver: Optional[str] = None


class PatchDocumentBody(BaseModel):
    title: Optional[str] = None
    doc_type: Optional[str] = None
    domain: Optional[str] = None
    function_tag: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None
    access_level: Optional[str] = None
    client_slug: Optional[str] = None
    source_url: Optional[str] = None


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
    for key in ("summary", "version", "owner", "embedding_status"):
        if row.get(key) is not None:
            out[key] = row[key]
    return out


def _document_response(row: Any) -> dict:
    """Build full document response with serializable values."""
    if not row:
        return {}
    result = dict(row)
    for k in list(result.keys()):
        v = result[k]
        if v is None:
            continue
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif hasattr(v, "hex"):
            result[k] = str(v)
    result["document_id"] = str(result.get("document_id"))
    return result


# ─── Upload (must be before /{document_id}) ───────────────────────────────


@router.post("/upload/url")
async def upload_url(
    body: UploadUrlBody,
    arq_pool: ArqRedis = Depends(get_arq_pool),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Create pending document; scrape, chunk and embed on ARQ worker. Returns 202 immediately."""
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of: {DOC_TYPES}")
    if body.domain == "general":
        raise HTTPException(status_code=400, detail="domain cannot be 'general'")

    pool = await get_db()
    approved_by = current_user.email or str(current_user.user_id)
    document_id = await insert_pending_document_row(
        pool,
        source_url=str(body.url),
        source_type="url",
        title=body.title or str(body.url),
        doc_type=body.doc_type,
        domain=body.domain,
        function_tag=body.function_tag,
        client_slug=body.client_slug,
        approved_by=approved_by,
        access_level=body.access_level or "reference",
        summary=body.summary,
        keywords=body.keywords,
    )
    try:
        await arq_pool.enqueue_job("process_knowledge_ingest", document_id, "", "")
    except Exception as e:
        logger.exception("enqueue process_knowledge_ingest failed for %s: %s", document_id, e)
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM knowledge_documents WHERE document_id = $1::uuid",
                document_id,
            )
        raise HTTPException(
            status_code=503,
            detail="Kon verwerking niet in de wachtrij zetten; probeer opnieuw.",
        ) from e

    return JSONResponse(
        status_code=202,
        content={
            "document_id": document_id,
            "status": "pending",
            "chunks_stored": 0,
            "embedding_status": "pending",
        },
    )


@router.post("/upload")
async def upload_file(
    arq_pool: ArqRedis = Depends(get_arq_pool),
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: str = Form("sop"),
    domain: str = Form(...),
    function_tag: str = Form("general"),
    client_slug: Optional[str] = Form(None),
    access_level: str = Form("reference"),
    summary: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Stream file to temp; pending row; extract/chunk/embed on ARQ worker. Returns 202."""
    pool = await get_db()
    filename = file.filename or "document"
    max_bytes = 10 * 1024 * 1024

    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of: {DOC_TYPES}")
    if not domain or domain == "general":
        raise HTTPException(status_code=400, detail="domain is required and cannot be 'general'")

    raw = await file.read()
    if len(raw) > max_bytes:
        raise HTTPException(status_code=400, detail="Bestand mag maximaal 10MB zijn")

    suffix = os.path.splitext(filename)[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    try:
        tmp.write(raw)
        tmp.close()
    except Exception:
        try:
            tmp.close()
        except Exception:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise HTTPException(status_code=400, detail="Failed to store upload")

    kw_list = None
    if keywords:
        try:
            kw_list = json.loads(keywords) if isinstance(keywords, str) else keywords
        except json.JSONDecodeError:
            kw_list = [k.strip() for k in keywords.split(",") if k.strip()] if isinstance(keywords, str) else []

    approved_by = current_user.email or str(current_user.user_id)
    document_id = await insert_pending_document_row(
        pool,
        source_url=None,
        source_type="file",
        title=title or filename,
        doc_type=doc_type,
        domain=domain,
        function_tag=function_tag,
        client_slug=client_slug,
        approved_by=approved_by,
        access_level=access_level or "reference",
        summary=summary,
        keywords=kw_list,
    )
    try:
        await arq_pool.enqueue_job("process_knowledge_ingest", document_id, tmp_path, filename)
    except Exception as e:
        logger.exception("enqueue process_knowledge_ingest (file) failed for %s: %s", document_id, e)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM knowledge_documents WHERE document_id = $1::uuid",
                document_id,
            )
        raise HTTPException(
            status_code=503,
            detail="Kon verwerking niet in de wachtrij zetten; probeer opnieuw.",
        ) from e

    return JSONResponse(
        status_code=202,
        content={
            "document_id": document_id,
            "status": "pending",
            "chunks_stored": 0,
            "embedding_status": "pending",
        },
    )


# ─── List & get (existing) ────────────────────────────────────────────────


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
                   doc_type, domain, status, summary, version, owner, created_at, updated_at,
                   embedding_status
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
                   doc_type, domain, status, summary, version, owner, created_at, updated_at,
                   embedding_status
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
            "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = $1 AND is_active = true",
            document_id,
        )
        chunk_rows = await conn.fetch(
            """
            SELECT chunk_index, chunk_text
            FROM knowledge_chunks
            WHERE document_id = $1 AND is_active = true
            ORDER BY chunk_index ASC
            """,
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
    doc["chunks"] = [
        {"chunk_index": int(r["chunk_index"]), "chunk_text": r["chunk_text"] or ""}
        for r in chunk_rows
    ]
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


# ─── PATCH, approve, archive, reindex, replace-content ─────────────────────


@router.patch("/{document_id}")
async def patch_document(
    document_id: UUID,
    body: PatchDocumentBody,
    arq_pool: ArqRedis = Depends(get_arq_pool),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Update document metadata. If source_url changed (URL docs): deactivate chunks + run reindex in background."""
    pool = await get_db()
    doc_id_str = str(document_id)
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            "SELECT * FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        updates = []
        values = []
        idx = 1

        if doc["status"] == "approved":
            updates.append("status = $1")
            values.append("draft")
            idx += 1
            updates.append("version = version + 1")
            await conn.execute(
                "UPDATE knowledge_chunks SET is_active = false WHERE document_id = $1",
                document_id,
            )

        dump = body.model_dump(exclude_unset=True)
        source_url_new = dump.pop("source_url", None)
        for field, val in dump.items():
            if val is not None:
                updates.append(f"{field} = ${idx}")
                values.append(val)
                idx += 1

        if source_url_new is not None:
            updates.append("source_url = ${idx}")
            values.append(source_url_new)
            idx += 1

        if updates:
            updates.append("updated_at = NOW()")
            values.append(document_id)
            placeholders = len(values)
            await conn.execute(
                f"UPDATE knowledge_documents SET {', '.join(updates)} WHERE document_id = ${placeholders}",
                *values,
            )

    # If source_url was changed and doc is URL-sourced, trigger reindex in background
    trigger_reindex = (
        source_url_new is not None
        and doc["source_type"] == "url"
        and (doc["source_url"] or "") != (source_url_new or "")
    )
    if trigger_reindex:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE knowledge_chunks SET is_active = false WHERE document_id = $1",
                document_id,
            )
            await conn.execute(
                "UPDATE knowledge_documents SET embedding_status = 'pending' WHERE document_id = $1",
                document_id,
            )
        try:
            await arq_pool.enqueue_job("reindex_document", doc_id_str)
        except Exception:
            pass

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
    return _document_response(row)


@router.post("/{document_id}/approve")
async def approve_document(
    document_id: UUID,
    body: ApproveBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Approve draft or stale document. 4-eyes required for policy docs."""
    pool = await get_db()
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            "SELECT * FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        status = doc["status"]
        if status not in ("draft", "stale"):
            raise HTTPException(
                status_code=400,
                detail="only draft or stale documents can be approved",
            )

        doc_type = doc["doc_type"]
        if doc_type == "policy":
            if not body.second_approver:
                raise HTTPException(
                    status_code=400,
                    detail="policy documents require second_approver",
                )
            if body.second_approver == current_user.user_id:
                raise HTTPException(
                    status_code=400,
                    detail="second_approver must differ from current user",
                )

        now = datetime.now(timezone.utc)
        approved_by = current_user.email or str(current_user.user_id)
        await conn.execute(
            """
            UPDATE knowledge_documents
            SET status = $1, approved_by = $2, approved_at = $3, last_reviewed = $4,
                second_approver = COALESCE($5, second_approver), updated_at = $6
            WHERE document_id = $7
            """,
            "approved",
            approved_by,
            now,
            now,
            body.second_approver if doc_type == "policy" else None,
            now,
            document_id,
        )

        doc_after = await conn.fetchrow(
            "SELECT * FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
        snapshot = dict(doc_after) if doc_after else {}

        def _json_serial_default(o: Any) -> Any:
            if hasattr(o, "isoformat"):
                return o.isoformat()
            if hasattr(o, "hex"):
                return str(o)
            raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

        await conn.execute(
            """
            INSERT INTO knowledge_versions
                (document_id, version, change_note, created_by, approved_by, snapshot)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            document_id,
            doc["version"],
            body.change_note or "approved",
            approved_by,
            approved_by,
            json.dumps(snapshot, default=_json_serial_default),
        )

    return {
        "document_id": str(document_id),
        "status": "approved",
        "version": doc["version"],
        "approved_at": now.isoformat(),
    }


@router.post("/{document_id}/archive")
async def archive_document(
    document_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Archive document and deactivate chunks."""
    pool = await get_db()
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            "SELECT document_id FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        await conn.execute(
            "UPDATE knowledge_documents SET status = $1, updated_at = NOW() WHERE document_id = $2",
            "archived",
            document_id,
        )
        await conn.execute(
            "UPDATE knowledge_chunks SET is_active = false WHERE document_id = $1",
            document_id,
        )

    return {"document_id": str(document_id), "status": "archived"}


@router.post("/{document_id}/reindex")
async def reindex_knowledge_document(
    document_id: UUID,
    arq_pool: ArqRedis = Depends(get_arq_pool),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Queue URL re-fetch + re-chunk + re-embed on worker. URL-sourced docs only. Returns 202."""
    pool = await get_db()
    doc_id_str = str(document_id)
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            """
            SELECT document_id, source_type, source_url
            FROM knowledge_documents
            WHERE document_id = $1
            """,
            document_id,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc["source_type"] != "url" or not (doc.get("source_url") or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Reindex only supported for URL-sourced documents",
            )
        await conn.execute(
            "UPDATE knowledge_documents SET embedding_status = 'pending', updated_at = now() WHERE document_id = $1",
            document_id,
        )
    try:
        await arq_pool.enqueue_job("reindex_document", doc_id_str)
    except Exception as e:
        logger.exception("enqueue reindex_document failed for %s: %s", doc_id_str, e)
        raise HTTPException(
            status_code=503,
            detail="Kon herindexering niet in de wachtrij zetten; probeer opnieuw.",
        ) from e

    return JSONResponse(
        status_code=202,
        content={"document_id": doc_id_str, "status": "pending", "embedding_status": "pending"},
    )


@router.post("/{document_id}/replace-content")
async def replace_content(
    document_id: UUID,
    arq_pool: ArqRedis = Depends(get_arq_pool),
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    domain: Optional[str] = Form(None),
    function_tag: Optional[str] = Form(None),
    access_level: Optional[str] = Form(None),
    summary: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    client_slug: Optional[str] = Form(None),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Stream file to worker: extract, re-chunk, embed on ARQ. Metadata updated sync. Returns 202."""
    pool = await get_db()
    doc_id_str = str(document_id)
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            "SELECT * FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc["status"] == "archived":
            raise HTTPException(status_code=400, detail="Cannot replace content of archived document")

    filename = file.filename or "document"
    max_bytes = 10 * 1024 * 1024
    raw = await file.read()
    if len(raw) > max_bytes:
        raise HTTPException(status_code=400, detail="Bestand mag maximaal 10MB zijn")

    suffix = os.path.splitext(filename)[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    try:
        tmp.write(raw)
        tmp.close()
    except Exception:
        try:
            tmp.close()
        except Exception:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise HTTPException(status_code=400, detail="Failed to store upload")

    # Optional metadata update (before worker replaces body)
    updates = []
    values = []
    idx = 1
    if title is not None:
        updates.append("title = $%d" % idx)
        values.append(title)
        idx += 1
    if doc_type is not None:
        updates.append("doc_type = $%d" % idx)
        values.append(doc_type)
        idx += 1
    if domain is not None:
        updates.append("domain = $%d" % idx)
        values.append(domain)
        idx += 1
    if function_tag is not None:
        updates.append("function_tag = $%d" % idx)
        values.append(function_tag)
        idx += 1
    if access_level is not None:
        updates.append("access_level = $%d" % idx)
        values.append(access_level)
        idx += 1
    if summary is not None:
        updates.append("summary = $%d" % idx)
        values.append(summary)
        idx += 1
    if keywords is not None:
        kw_list = json.loads(keywords) if isinstance(keywords, str) and keywords.strip() else []
        updates.append("keywords = $%d" % idx)
        values.append(kw_list)
        idx += 1
    if client_slug is not None:
        updates.append("client_slug = $%d" % idx)
        values.append(client_slug or None)
        idx += 1
    if updates:
        values.append(document_id)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE knowledge_documents SET " + ", ".join(updates) + ", updated_at = NOW() WHERE document_id = $%d" % idx,
                *values,
            )

    try:
        await arq_pool.enqueue_job("process_knowledge_replace_content", doc_id_str, tmp_path, filename)
    except Exception as e:
        logger.exception("enqueue process_knowledge_replace_content failed for %s: %s", doc_id_str, e)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=503,
            detail="Kon verwerking niet in de wachtrij zetten; probeer opnieuw.",
        ) from e

    return JSONResponse(
        status_code=202,
        content={
            "document_id": doc_id_str,
            "status": "pending",
            "embedding_status": "pending",
        },
    )
