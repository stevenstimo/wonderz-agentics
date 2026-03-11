"""Knowledge Centre API — upload, retrieval, approval flow, Library UI.

POST /api/knowledge/upload — file upload
POST /api/knowledge/upload/url — URL ingest
GET /api/knowledge — list documents (Library UI)
GET /api/knowledge/{document_id} — document detail + versions + chunk_count
POST /api/knowledge/{document_id}/approve — approve draft/stale
POST /api/knowledge/{document_id}/archive — archive document
PATCH /api/knowledge/{document_id} — update metadata
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, HttpUrl

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user
from app.services.knowledge_upload_service import (
    DOC_TYPES,
    upload_document_from_text,
)
from app.services.training import TrainingError, extract_text, scrape_url
from app.utils.document_parser import extract_text_from_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


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


@router.post("/upload/url")
async def upload_url(
    body: UploadUrlBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Ingest document from URL. Scrape, chunk, embed, store."""
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of: {DOC_TYPES}")
    if body.domain == "general":
        raise HTTPException(status_code=400, detail="domain cannot be 'general'")

    try:
        html = await scrape_url(str(body.url))
        text = extract_text(html)
    except TrainingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not text or len(text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Could not extract enough text from URL")

    pool = await get_db()
    try:
        result = await upload_document_from_text(
            pool,
            text,
            source_url=str(body.url),
            source_type="url",
            title=body.title or str(body.url),
            doc_type=body.doc_type,
            domain=body.domain,
            function_tag=body.function_tag,
            client_slug=body.client_slug,
            approved_by=current_user.email or str(current_user.user_id),
            access_level=body.access_level or "reference",
            summary=body.summary,
            keywords=body.keywords,
        )
    except TrainingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.post("/upload")
async def upload_file(
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
    """Upload document (PDF, docx, txt, md, csv, xlsx). Chunk, embed, store."""
    pool = await get_db()
    filename = file.filename or "document"
    try:
        raw = await file.read()
        text = extract_text_from_file(filename, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Upload read failed: %s", e)
        raise HTTPException(status_code=400, detail="Failed to read file")

    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of: {DOC_TYPES}")
    if not domain or domain == "general":
        raise HTTPException(status_code=400, detail="domain is required and cannot be 'general'")

    kw_list = None
    if keywords:
        try:
            kw_list = json.loads(keywords) if isinstance(keywords, str) else keywords
        except json.JSONDecodeError:
            kw_list = [k.strip() for k in keywords.split(",") if k.strip()] if isinstance(keywords, str) else []

    try:
        result = await upload_document_from_text(
            pool,
            text,
            source_url=None,
            source_type="file",
            title=title or filename,
            doc_type=doc_type,
            domain=domain,
            function_tag=function_tag,
            client_slug=client_slug,
            approved_by=current_user.email or str(current_user.user_id),
            access_level=access_level or "reference",
            summary=summary,
            keywords=kw_list,
        )
    except TrainingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


# ─── DEEL A: Approval flow ───────────────────────────────────────────────


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


@router.post("/{document_id}/approve")
async def approve_document(
    document_id: str,
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
        approved_by = current_user.user_id
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
        for k, v in list(snapshot.items()):
            if hasattr(v, "isoformat"):
                snapshot[k] = v.isoformat() if v else None

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
            json.dumps(snapshot),
        )

    return {
        "document_id": document_id,
        "status": "approved",
        "version": doc["version"],
        "approved_at": now.isoformat(),
    }


@router.post("/{document_id}/archive")
async def archive_document(
    document_id: str,
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

    return {"document_id": document_id, "status": "archived"}


@router.patch("/{document_id}")
async def patch_document(
    document_id: str,
    body: PatchDocumentBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Update document metadata. If approved → reset to draft, version+1, chunks inactive."""
    pool = await get_db()
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

        for field, val in body.model_dump(exclude_unset=True).items():
            if val is not None:
                updates.append(f"{field} = ${idx}")
                values.append(val)
                idx += 1

        if updates:
            updates.append("updated_at = NOW()")
            values.append(document_id)
            placeholders = len(values)
            await conn.execute(
                f"UPDATE knowledge_documents SET {', '.join(updates)} WHERE document_id = ${placeholders}",
                *values,
            )

        row = await conn.fetchrow(
            "SELECT document_id, version, status FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
    return {
        "document_id": str(row["document_id"]),
        "version": row["version"],
        "status": row["status"],
    }


# ─── DEEL B: Governance endpoints ────────────────────────────────────────


@router.post("/governance/run-stale-detection")
async def run_stale_detection(
    current_user: TokenPayload = Depends(get_current_user),
):
    """Manually trigger stale detection. Returns marked_stale + already_stale + duration."""
    import time

    from app.services.stale_detection import StaleDetectionService

    pool = await get_db()
    t0 = time.monotonic()
    result = await StaleDetectionService().run(pool)
    duration_ms = int((time.monotonic() - t0) * 1000)
    return {**result, "duration_ms": duration_ms}


@router.get("/governance/queue")
async def governance_queue(
    current_user: TokenPayload = Depends(get_current_user),
):
    """Draft + stale documents for approval queue. Sorted by updated_at ASC."""
    pool = await get_db()
    async with pool.acquire() as conn:
        draft_rows = await conn.fetch(
            """
            SELECT document_id, title, doc_type, domain, status, access_level,
                   client_slug, version, created_at, updated_at, approved_at,
                   summary, last_reviewed, review_interval_days
            FROM knowledge_documents
            WHERE status IN ('draft', 'stale')
            ORDER BY updated_at ASC
            LIMIT 200
            """
        )
        draft_count = await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge_documents WHERE status = 'draft'"
        )
        stale_count = await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge_documents WHERE status = 'stale'"
        )

    def _row(r):
        return {
            "document_id": str(r["document_id"]),
            "title": r["title"],
            "doc_type": r["doc_type"],
            "domain": r["domain"],
            "status": r["status"],
            "access_level": r["access_level"],
            "client_slug": r["client_slug"],
            "version": r["version"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            "approved_at": r["approved_at"].isoformat() if r["approved_at"] else None,
            "summary": r["summary"],
            "last_reviewed": r["last_reviewed"].isoformat() if r.get("last_reviewed") else None,
            "review_interval_days": r.get("review_interval_days"),
        }

    return {
        "total": len(draft_rows),
        "draft": draft_count or 0,
        "stale": stale_count or 0,
        "documents": [_row(r) for r in draft_rows],
    }


@router.get("/governance/audit")
async def governance_audit(
    current_user: TokenPayload = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Audit log from knowledge_versions."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                kv.version_id,
                kv.document_id,
                kd.title,
                kd.doc_type,
                kv.version,
                kv.change_note,
                kv.created_by,
                kv.approved_by,
                kv.created_at
            FROM knowledge_versions kv
            JOIN knowledge_documents kd ON kv.document_id = kd.document_id
            ORDER BY kv.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )

    return [
        {
            "version_id": str(r["version_id"]),
            "document_id": str(r["document_id"]),
            "title": r["title"],
            "doc_type": r["doc_type"],
            "version": r["version"],
            "change_note": r["change_note"],
            "created_by": r["created_by"],
            "approved_by": r["approved_by"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


class PermissionCreate(BaseModel):
    agent_id: Optional[str] = None
    role: Optional[str] = None
    domain: Optional[str] = None
    document_id: Optional[str] = None
    permission_level: str = Field(..., description="read|write|admin|none")
    valid_until: Optional[str] = None


@router.get("/permissions")
async def list_permissions(
    current_user: TokenPayload = Depends(get_current_user),
):
    """List all knowledge_permissions with optional doc title."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT kp.permission_id, kp.agent_id, kp.role, kp.domain, kp.document_id,
                   kp.permission_level, kp.granted_by, kp.valid_until, kp.created_at,
                   kd.title AS doc_title
            FROM knowledge_permissions kp
            LEFT JOIN knowledge_documents kd ON kp.document_id = kd.document_id
            ORDER BY kp.created_at DESC
            """
        )

    return [
        {
            "permission_id": str(r["permission_id"]),
            "agent_id": r["agent_id"],
            "role": r["role"],
            "domain": r["domain"],
            "document_id": str(r["document_id"]) if r["document_id"] else None,
            "doc_title": r["doc_title"],
            "permission_level": r["permission_level"],
            "granted_by": r["granted_by"],
            "valid_until": r["valid_until"].isoformat() if r.get("valid_until") else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.post("/permissions")
async def create_permission(
    body: PermissionCreate,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Create a new permission rule. agent_id or role required."""
    if not body.agent_id and not body.role:
        raise HTTPException(status_code=400, detail="agent_id or role required")

    if body.permission_level not in ("read", "write", "admin", "none"):
        raise HTTPException(status_code=400, detail="permission_level must be read|write|admin|none")

    pool = await get_db()
    async with pool.acquire() as conn:
        agent_id_val = body.agent_id
        if body.agent_id:
            exists = await conn.fetchval(
                "SELECT 1 FROM hired_agents WHERE agent_id = $1",
                body.agent_id,
            )
            if not exists:
                raise HTTPException(status_code=400, detail="agent_id not found")
        else:
            agent_id_val = None

        await conn.execute(
            """
            INSERT INTO knowledge_permissions
                (agent_id, role, domain, document_id, permission_level, granted_by, valid_until)
            VALUES ($1, $2, $3, $4::uuid, $5, $6, $7::timestamptz)
            """,
            agent_id_val,
            body.role or None,
            body.domain or None,
            body.document_id or None,
            body.permission_level,
            current_user.email or str(current_user.user_id),
            body.valid_until or None,
        )

    return {"status": "created"}


@router.delete("/permissions/{permission_id}")
async def delete_permission(
    permission_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Delete a permission rule."""
    pool = await get_db()
    async with pool.acquire() as conn:
        r = await conn.execute(
            "DELETE FROM knowledge_permissions WHERE permission_id = $1::uuid RETURNING 1",
            permission_id,
        )
        if r == "DELETE 0":
            raise HTTPException(status_code=404, detail="Permission not found")

    return {"status": "deleted"}


# ─── DEEL C: GET endpoints voor Library UI ───────────────────────────────


@router.get("")
async def list_documents(
    current_user: TokenPayload = Depends(get_current_user),
    domain: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    client_slug: Optional[str] = Query(None),
    function_tag: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List documents with filters. Default status excludes archived."""
    pool = await get_db()
    conditions = []
    params = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    else:
        conditions.append("status != 'archived'")
    if domain:
        conditions.append(f"domain = ${idx}")
        params.append(domain)
        idx += 1
    if doc_type:
        conditions.append(f"doc_type = ${idx}")
        params.append(doc_type)
        idx += 1
    if client_slug:
        conditions.append(f"client_slug = ${idx}")
        params.append(client_slug)
        idx += 1
    if function_tag:
        conditions.append(f"function_tag = ${idx}")
        params.append(function_tag)
        idx += 1
    if scope:
        if scope == "agency_wide":
            conditions.append("client_slug IS NULL")
        elif scope == "client_specific":
            conditions.append("client_slug IS NOT NULL")
        elif scope == "per_job":
            conditions.append("COALESCE(scope, '') = 'per_job'")
    if search:
        conditions.append(
            f"(title ILIKE ${idx} OR summary ILIKE ${idx} OR EXISTS (SELECT 1 FROM unnest(COALESCE(keywords, '{{}}')) k WHERE k ILIKE ${idx}))"
        )
        params.append(f"%{search}%")
        idx += 1

    where = " AND ".join(conditions)
    params.extend([limit, offset])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT document_id, title, doc_type, domain, status, access_level,
                   client_slug, version, created_at, updated_at, approved_at,
                   summary, keywords, function_tag, last_reviewed, review_interval_days,
                   CASE WHEN client_slug IS NOT NULL THEN 'client_specific' ELSE 'agency_wide' END AS scope
            FROM knowledge_documents
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )

    return [
        {
            "document_id": str(r["document_id"]),
            "title": r["title"],
            "doc_type": r["doc_type"],
            "domain": r["domain"],
            "status": r["status"],
            "access_level": r["access_level"],
            "client_slug": r["client_slug"],
            "version": r["version"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            "approved_at": r["approved_at"].isoformat() if r["approved_at"] else None,
            "summary": r["summary"],
            "keywords": r["keywords"] or [],
            "function_tag": r["function_tag"],
            "scope": r["scope"] or ("client_specific" if r["client_slug"] else "agency_wide"),
            "last_reviewed": r["last_reviewed"].isoformat() if r.get("last_reviewed") else None,
            "review_interval_days": r.get("review_interval_days"),
        }
        for r in rows
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Document detail with last 5 versions and chunk_count."""
    pool = await get_db()
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            "SELECT * FROM knowledge_documents WHERE document_id = $1",
            document_id,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        versions = await conn.fetch(
            """
            SELECT version_id, version, change_note, created_by, approved_by,
                   snapshot, created_at
            FROM knowledge_versions
            WHERE document_id = $1
            ORDER BY created_at DESC
            LIMIT 5
            """,
            document_id,
        )
        chunk_count = await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = $1 AND is_active = true",
            document_id,
        )

    def _serialize(obj: Any) -> Any:
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_serialize(v) for v in obj]
        return obj

    result = dict(doc)
    result["document_id"] = str(result["document_id"])
    for k in list(result.keys()):
        result[k] = _serialize(result[k])

    result["versions"] = []
    for v in versions:
        snap = v["snapshot"]
        if isinstance(snap, str):
            try:
                snap = json.loads(snap) if snap else {}
            except Exception:
                snap = {}
        result["versions"].append({
            "version_id": str(v["version_id"]),
            "version": v["version"],
            "change_note": v["change_note"],
            "created_by": v["created_by"],
            "approved_by": v["approved_by"],
            "snapshot": snap,
            "created_at": v["created_at"].isoformat() if v["created_at"] else None,
        })
    result["chunk_count"] = chunk_count or 0
    return result
