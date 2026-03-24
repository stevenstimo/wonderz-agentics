"""Knowledge Upload Service — document ingest voor AI Agency Knowledge Centre.

Pattern: fire-and-forget / Aanpak A — status via knowledge_documents.embedding_status;
zware stappen (URL-fetch, file-parse, chunk, embed) draaien in ARQ (`process_knowledge_ingest`, enz.).

Hergebruikt chunk_text en generate_embedding uit training.py.
Slaat op in knowledge_documents + knowledge_chunks (agency-wide of client-scoped).
Geen agent mag ooit zelf een document approven — approved_by is altijd user.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.services.training import (
    chunk_text,
    extract_text,
    generate_embedding,
    scrape_url,
    TrainingError,
)
from app.services.content_filter import filter_chunks
from app.utils.document_parser import extract_text_from_file

logger = logging.getLogger(__name__)

DOC_TYPES = (
    "playbook",
    "sop",
    "framework",
    "template",
    "case_study",
    "policy",
    "research",
    "client_context",
    "skill_spec",
)


async def create_document_with_chunks(
    pool,
    text: str,
    *,
    source_url: Optional[str] = None,
    source_type: str = "file",
    title: Optional[str] = None,
    doc_type: str = "sop",
    domain: str = "general",
    function_tag: str = "general",
    client_slug: Optional[str] = None,
    approved_by: str,
    access_level: str = "reference",
    summary: Optional[str] = None,
    keywords: Optional[list[str]] = None,
    chunk_size: int = 500,
    overlap: int = 50,
) -> dict[str, Any]:
    """
    Create document and chunks without embeddings. Sets embedding_status='pending'.
    Returns: {document_id, chunks_stored, status: "draft"} for 202 response.
    """
    if not text or len(text.strip()) < 50:
        raise TrainingError("Text too short for ingestion (min 50 chars)")

    chunks_tuples = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks_tuples:
        raise TrainingError("No chunks generated")

    chunks = [c[0] for c in chunks_tuples]
    chunks = await filter_chunks(chunks, context_hint=source_url or title or "", use_ai_filter=False)
    if not chunks:
        logger.warning("[FILTER] Geen bruikbare chunks na filtering (create_document_with_chunks)")
        raise TrainingError("Geen bruikbare chunks na inhoudsfilters")

    al = access_level if access_level in ("reference", "approved", "restricted") else "reference"
    kw = keywords if keywords else []

    async with pool.acquire() as conn:
        document_id = await conn.fetchval(
            """
            INSERT INTO knowledge_documents (
                source_url, source_type, title, client_slug,
                approved_by, doc_type, domain, function_tag, owner,
                status, access_level, summary, keywords, embedding_status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'draft', $10, $11, $12, 'pending')
            RETURNING document_id
            """,
            source_url,
            source_type,
            title or (source_url or "upload"),
            client_slug,
            approved_by,
            doc_type,
            domain,
            function_tag,
            approved_by,
            al,
            summary,
            kw,
        )

        for idx, chunk_text_val in enumerate(chunks):
            await conn.execute(
                """
                INSERT INTO knowledge_chunks
                    (document_id, chunk_text, chunk_index, embedding, is_active)
                VALUES ($1, $2, $3, NULL, true)
                """,
                document_id,
                chunk_text_val,
                idx,
            )

    logger.info(
        "Knowledge document created (pending embeddings): document_id=%s chunks=%s",
        document_id,
        len(chunks),
    )
    return {
        "document_id": str(document_id),
        "chunks_stored": len(chunks),
        "status": "draft",
    }


async def insert_pending_document_row(
    pool,
    *,
    source_url: Optional[str],
    source_type: str,
    title: str,
    doc_type: str,
    domain: str,
    function_tag: str,
    client_slug: Optional[str],
    approved_by: str,
    access_level: str,
    summary: Optional[str],
    keywords: Optional[list[str]],
) -> str:
    """Insert knowledge_documents row with embedding_status pending and no chunks (worker will ingest)."""
    al = access_level if access_level in ("reference", "approved", "restricted") else "reference"
    kw = keywords if keywords else []
    async with pool.acquire() as conn:
        document_id = await conn.fetchval(
            """
            INSERT INTO knowledge_documents (
                source_url, source_type, title, client_slug,
                approved_by, doc_type, domain, function_tag, owner,
                status, access_level, summary, keywords, embedding_status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'draft', $10, $11, $12, 'pending')
            RETURNING document_id
            """,
            source_url,
            source_type,
            title or (source_url or "upload"),
            client_slug,
            approved_by,
            doc_type,
            domain,
            function_tag,
            approved_by,
            al,
            summary,
            kw,
        )
    return str(document_id)


async def ingest_url_document_then_embed(pool, document_id: str) -> None:
    """Fetch URL row, scrape + chunk in worker, then run_embedding_task."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT document_id, source_url, source_type, embedding_status
            FROM knowledge_documents
            WHERE document_id = $1::uuid
            """,
            document_id,
        )
    if not row:
        logger.warning("ingest_url_document_then_embed: missing document %s", document_id)
        return
    if (row.get("source_type") or "") != "url" or not (row.get("source_url") or "").strip():
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        logger.warning("ingest_url_document_then_embed: invalid source for %s", document_id)
        return
    try:
        html = await scrape_url(row["source_url"])
        text = extract_text(html)
    except TrainingError as e:
        logger.warning("ingest_url scrape failed %s: %s", document_id, e)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return
    if not text or len(text.strip()) < 50:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return
    chunks_tuples = chunk_text(text, chunk_size=500, overlap=50)
    if not chunks_tuples:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return
    chunks = [c[0] for c in chunks_tuples]
    chunks = await filter_chunks(chunks, context_hint=row["source_url"] or "", use_ai_filter=False)
    if not chunks:
        logger.warning("[FILTER] Geen bruikbare chunks na filtering (ingest_url) document_id=%s", document_id)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM knowledge_chunks WHERE document_id = $1::uuid",
            document_id,
        )
        for idx, chunk_text_val in enumerate(chunks):
            await conn.execute(
                """
                INSERT INTO knowledge_chunks
                    (document_id, chunk_text, chunk_index, embedding, is_active)
                VALUES ($1::uuid, $2, $3, NULL, true)
                """,
                document_id,
                chunk_text_val,
                idx,
            )
    await run_embedding_task(pool, document_id)


async def ingest_file_from_temp_then_embed(
    pool, document_id: str, tmp_path: str, original_filename: str
) -> None:
    """Read temp file, chunk, store chunks, embed; caller deletes tmp_path."""
    try:
        with open(tmp_path, "rb") as f:
            raw = f.read()
        text = extract_text_from_file(original_filename or "upload", raw)
    except ValueError as e:
        logger.warning("ingest_file parse failed %s: %s", document_id, e)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return
    except OSError as e:
        logger.warning("ingest_file read failed %s: %s", document_id, e)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return

    if not text or len(text.strip()) < 50:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return
    chunks_tuples = chunk_text(text, chunk_size=500, overlap=50)
    if not chunks_tuples:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return
    chunks = [c[0] for c in chunks_tuples]
    chunks = await filter_chunks(chunks, context_hint=original_filename or "", use_ai_filter=False)
    if not chunks:
        logger.warning("[FILTER] Geen bruikbare chunks na filtering (ingest_file) document_id=%s", document_id)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM knowledge_chunks WHERE document_id = $1::uuid",
            document_id,
        )
        for idx, chunk_text_val in enumerate(chunks):
            await conn.execute(
                """
                INSERT INTO knowledge_chunks
                    (document_id, chunk_text, chunk_index, embedding, is_active)
                VALUES ($1::uuid, $2, $3, NULL, true)
                """,
                document_id,
                chunk_text_val,
                idx,
            )
    await run_embedding_task(pool, document_id)


async def run_embedding_task(pool, document_id: str) -> None:
    """
    Background task: set embedding_status to processing, generate embeddings for all
    chunks of the document, update chunks and set embedding_status to complete or failed.
    """
    # #region agent log
    try:
        import time
        payload = {
            "sessionId": "0ce1b2",
            "runId": "pre_debug",
            "hypothesisId": "H2",
            "location": "knowledge_upload_service.py:run_embedding_task:start",
            "message": "run_embedding_task started",
            "data": {"document_id": document_id},
            "timestamp": int(time.time() * 1000),
        }
        with open("/home/exedev/wonderz-agentics/.cursor/debug-0ce1b2.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
    # #endregion
    async with pool.acquire() as conn:
        update_result = await conn.execute(
            """
            UPDATE knowledge_documents
            SET embedding_status = 'processing', updated_at = now()
            WHERE document_id = $1::uuid AND embedding_status = 'pending'
            """,
            document_id,
        )
        rows = await conn.fetch(
            """
            SELECT chunk_id, chunk_text
            FROM knowledge_chunks
            WHERE document_id = $1::uuid AND is_active = true
            ORDER BY chunk_index ASC
            """,
            document_id,
        )
    # #region agent log
    try:
        import time
        payload = {
            "sessionId": "0ce1b2",
            "runId": "pre_debug",
            "hypothesisId": "H4",
            "location": "knowledge_upload_service.py:run_embedding_task:after_update_fetch",
            "message": "embedding_status update + chunk fetch done",
            "data": {"document_id": document_id, "update_result": str(update_result), "chunks_found": len(rows)},
            "timestamp": int(time.time() * 1000),
        }
        with open("/home/exedev/wonderz-agentics/.cursor/debug-0ce1b2.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
    # #endregion

    if not rows:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE knowledge_documents SET embedding_status = 'failed', updated_at = now() WHERE document_id = $1::uuid",
                document_id,
            )
        logger.warning("run_embedding_task: no chunks for document_id=%s", document_id)
        return

    try:
        first_chunk = True
        for row in rows:
            chunk_id = row["chunk_id"]
            chunk_text_val = (row["chunk_text"] or "")[:8000]
            if first_chunk:
                # Log first embedding to detect hangs/crashes early.
                import time
                t0_ms = int(time.time() * 1000)
                try:
                    payload = {
                        "sessionId": "0ce1b2",
                        "runId": "pre_debug",
                        "hypothesisId": "H1",
                        "location": "knowledge_upload_service.py:run_embedding_task:first_chunk_embed_start",
                        "message": "first chunk embedding start",
                        "data": {"document_id": document_id, "chunk_id": str(chunk_id), "chunk_chars": len(chunk_text_val)},
                        "timestamp": t0_ms,
                    }
                    with open("/home/exedev/wonderz-agentics/.cursor/debug-0ce1b2.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps(payload) + "\n")
                except Exception:
                    pass
            embedding = await generate_embedding(chunk_text_val)
            if first_chunk:
                # Log duration of the first embedding call only (avoid log spam).
                try:
                    import time
                    t1_ms = int(time.time() * 1000)
                    payload = {
                        "sessionId": "0ce1b2",
                        "runId": "pre_debug",
                        "hypothesisId": "H1",
                        "location": "knowledge_upload_service.py:run_embedding_task:first_chunk_embed_done",
                        "message": "first chunk embedding done",
                        "data": {"document_id": document_id, "chunk_id": str(chunk_id), "duration_ms": t1_ms - t0_ms, "embedding_dim": len(embedding) if hasattr(embedding, '__len__') else None},
                        "timestamp": t1_ms,
                    }
                    with open("/home/exedev/wonderz-agentics/.cursor/debug-0ce1b2.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps(payload) + "\n")
                except Exception:
                    pass
                first_chunk = False
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE knowledge_chunks
                    SET embedding = $1::vector
                    WHERE chunk_id = $2
                    """,
                    json.dumps(embedding),
                    chunk_id,
                )

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'complete', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )
        # #region agent log
        try:
            import time
            payload = {
                "sessionId": "0ce1b2",
                "runId": "pre_debug",
                "hypothesisId": "H1",
                "location": "knowledge_upload_service.py:run_embedding_task:complete",
                "message": "run_embedding_task complete",
                "data": {"document_id": document_id, "chunks": len(rows)},
                "timestamp": int(time.time() * 1000),
            }
            with open("/home/exedev/wonderz-agentics/.cursor/debug-0ce1b2.log", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            pass
        # #endregion
        logger.info("run_embedding_task: complete document_id=%s chunks=%s", document_id, len(rows))
    except Exception as exc:
        logger.exception("run_embedding_task failed document_id=%s: %s", document_id, exc)
        # #region agent log
        try:
            import time
            payload = {
                "sessionId": "0ce1b2",
                "runId": "pre_debug",
                "hypothesisId": "H1",
                "location": "knowledge_upload_service.py:run_embedding_task:exception",
                "message": "run_embedding_task exception",
                "data": {"document_id": document_id, "exc_type": type(exc).__name__, "exc": str(exc)[:300]},
                "timestamp": int(time.time() * 1000),
            }
            with open("/home/exedev/wonderz-agentics/.cursor/debug-0ce1b2.log", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            pass
        # #endregion
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET embedding_status = 'failed', updated_at = now()
                WHERE document_id = $1::uuid
                """,
                document_id,
            )


async def replace_document_content_from_text(
    pool,
    document_id: str,
    text: str,
    *,
    chunk_size: int = 500,
    overlap: int = 50,
) -> int:
    """
    Replace chunks for an existing document: set embedding_status pending, deactivate old chunks,
    insert new chunks from text. Caller should then run_embedding_task in background.
    Returns number of chunks stored.
    """
    if not text or len(text.strip()) < 50:
        raise TrainingError("Text too short for ingestion (min 50 chars)")
    chunks_tuples = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks_tuples:
        raise TrainingError("No chunks generated")
    chunks = [c[0] for c in chunks_tuples]
    chunks = await filter_chunks(chunks, context_hint="", use_ai_filter=False)
    if not chunks:
        logger.warning("[FILTER] Geen bruikbare chunks na filtering (replace_document) document_id=%s", document_id)
        raise TrainingError("Geen bruikbare chunks na inhoudsfilters")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_documents
            SET embedding_status = 'pending', updated_at = NOW()
            WHERE document_id = $1::uuid
            """,
            document_id,
        )
        await conn.execute(
            "UPDATE knowledge_chunks SET is_active = false WHERE document_id = $1::uuid",
            document_id,
        )
        for idx, chunk_text_val in enumerate(chunks):
            await conn.execute(
                """
                INSERT INTO knowledge_chunks
                    (document_id, chunk_text, chunk_index, embedding, is_active)
                VALUES ($1::uuid, $2, $3, NULL, true)
                """,
                document_id,
                chunk_text_val,
                idx,
            )
    logger.info("replace_document_content: document_id=%s chunks=%s", document_id, len(chunks))
    return len(chunks)


async def reindex_document(
    pool,
    document_id: str,
    *,
    chunk_size: int = 500,
    overlap: int = 50,
) -> dict[str, Any]:
    """
    Re-fetch (URL only), re-chunk and re-embed a document. Deactivates existing chunks
    and inserts new ones. Sets embedding_status to processing/complete/failed for polling.
    Only supported for source_type='url' with source_url set.
    Returns: {chunks_created: int}
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT document_id, source_url, source_type
            FROM knowledge_documents
            WHERE document_id = $1::uuid
            """,
            document_id,
        )
        if not row:
            raise TrainingError("Document not found")
        if row["source_type"] != "url" or not row["source_url"]:
            raise TrainingError(
                "Reindex only supported for URL-sourced documents; re-upload file documents to re-chunk."
            )

        await conn.execute(
            "UPDATE knowledge_documents SET embedding_status = 'processing', updated_at = now() WHERE document_id = $1::uuid",
            document_id,
        )

        html = await scrape_url(row["source_url"])
        text = extract_text(html)
        if not text or len(text.strip()) < 50:
            await conn.execute(
                "UPDATE knowledge_documents SET embedding_status = 'failed', updated_at = now() WHERE document_id = $1::uuid",
                document_id,
            )
            raise TrainingError("Could not extract enough text from URL")

        await conn.execute(
            "UPDATE knowledge_chunks SET is_active = false WHERE document_id = $1::uuid",
            document_id,
        )

        chunks_tuples = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks_tuples:
            await conn.execute(
                "UPDATE knowledge_documents SET embedding_status = 'failed', updated_at = now() WHERE document_id = $1::uuid",
                document_id,
            )
            raise TrainingError("No chunks generated")
        chunks = [c[0] for c in chunks_tuples]
        chunks = await filter_chunks(chunks, context_hint=row["source_url"] or "", use_ai_filter=False)
        if not chunks:
            logger.warning("[FILTER] Geen bruikbare chunks na filtering (reindex) document_id=%s", document_id)
            await conn.execute(
                "UPDATE knowledge_documents SET embedding_status = 'failed', updated_at = now() WHERE document_id = $1::uuid",
                document_id,
            )
            raise TrainingError("Geen bruikbare chunks na inhoudsfilters")

        try:
            for idx, chunk_text_val in enumerate(chunks):
                embedding = await generate_embedding((chunk_text_val or "")[:8000])
                await conn.execute(
                    """
                    INSERT INTO knowledge_chunks
                        (document_id, chunk_text, chunk_index, embedding, is_active)
                    VALUES ($1::uuid, $2, $3, $4::vector, true)
                    """,
                    document_id,
                    chunk_text_val,
                    idx,
                    json.dumps(embedding),
                )
            await conn.execute(
                "UPDATE knowledge_documents SET embedding_status = 'complete', updated_at = now() WHERE document_id = $1::uuid",
                document_id,
            )
        except Exception as exc:
            logger.exception("reindex_document failed: %s", exc)
            await conn.execute(
                "UPDATE knowledge_documents SET embedding_status = 'failed', updated_at = now() WHERE document_id = $1::uuid",
                document_id,
            )
            raise

    logger.info("Knowledge reindex: document_id=%s chunks_created=%s", document_id, len(chunks))
    return {"chunks_created": len(chunks)}


async def upload_document_from_text(
    pool,
    text: str,
    *,
    source_url: Optional[str] = None,
    source_type: str = "file",
    title: Optional[str] = None,
    doc_type: str = "sop",
    domain: str = "general",
    function_tag: str = "general",
    client_slug: Optional[str] = None,
    approved_by: str,
    access_level: str = "reference",
    summary: Optional[str] = None,
    keywords: Optional[list[str]] = None,
    chunk_size: int = 500,
    overlap: int = 50,
) -> dict[str, Any]:
    """
    Parse text, chunk, embed, store in knowledge_documents + knowledge_chunks.
    approved_by: user identifier (nooit agent).
    Returns: {document_id, chunks_stored, status}
    """
    if not text or len(text.strip()) < 50:
        raise TrainingError("Text too short for ingestion (min 50 chars)")

    chunks_tuples = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks_tuples:
        raise TrainingError("No chunks generated")

    chunks = [c[0] for c in chunks_tuples]
    chunks = await filter_chunks(chunks, context_hint=source_url or title or "", use_ai_filter=False)
    if not chunks:
        logger.warning("[FILTER] Geen bruikbare chunks na filtering (upload_document_from_text)")
        raise TrainingError("Geen bruikbare chunks na inhoudsfilters")

    al = access_level if access_level in ("reference", "approved", "restricted") else "reference"
    kw = keywords if keywords else []

    async with pool.acquire() as conn:
        document_id = await conn.fetchval(
            """
            INSERT INTO knowledge_documents (
                source_url, source_type, title, client_slug,
                approved_by, doc_type, domain, function_tag, owner,
                status, access_level, summary, keywords
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'draft', $10, $11, $12)
            RETURNING document_id
            """,
            source_url,
            source_type,
            title or (source_url or "upload"),
            client_slug,
            approved_by,
            doc_type,
            domain,
            function_tag,
            approved_by,
            al,
            summary,
            kw,
        )

        stored = 0
        for idx, chunk_text_val in enumerate(chunks):
            embedding = await generate_embedding((chunk_text_val or "")[:8000])
            await conn.execute(
                """
                INSERT INTO knowledge_chunks
                    (document_id, chunk_text, chunk_index, embedding, is_active)
                VALUES ($1, $2, $3, $4::vector, true)
                """,
                document_id,
                chunk_text_val,
                idx,
                json.dumps(embedding),
            )
            stored += 1

    logger.info(
        "Knowledge upload: document_id=%s chunks=%s approved_by=%s",
        document_id,
        stored,
        approved_by,
    )
    return {
        "document_id": str(document_id),
        "chunks_stored": stored,
        "status": "draft",
    }
