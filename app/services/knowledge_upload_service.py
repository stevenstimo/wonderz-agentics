"""Knowledge Upload Service — document ingest voor AI Agency Knowledge Centre.

Hergebruikt chunk_text en generate_embedding uit training.py.
Slaat op in knowledge_documents + knowledge_chunks (agency-wide of client-scoped).
Geen agent mag ooit zelf een document approven — approved_by is altijd user.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.services.training import chunk_text, generate_embedding, TrainingError

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
