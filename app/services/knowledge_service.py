"""Knowledge Service — AI Agency Knowledge Centre.

Haalt relevante chunks op voor agents uit knowledge_chunks + knowledge_documents.
Agency-wide en client_context altijd GESCHEIDEN (spec: client_context apart ophalen).
Hergebruikt generate_embedding() uit training.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.database import get_db
from app.services.training import generate_embedding

logger = logging.getLogger(__name__)

# Spec §5.1 — prioriteit volgorde (doc_type, access_level)
PRIORITY_ORDER = [
    ("policy", "approved"),
    ("playbook", "approved"),
    ("sop", "approved"),
    ("framework", "approved"),
    ("template", "approved"),
    ("skill_spec", "approved"),
    ("client_context", "approved"),
    ("case_study", "reference"),
    ("research", "reference"),
]

# Token budget per doc_type (schat via word_count * 1.3)
TOKEN_BUDGET_BY_TYPE = {
    "policy": 500,
    "playbook": 2000,
    "sop": 2000,
    "framework": 2000,
    "client_context": 1500,
    "template": 800,
    "skill_spec": 800,
}
TOKEN_BUDGET_DEFAULT = 600
TOKEN_BUDGET_TOTAL_MAX = 6000


def _estimate_tokens(text: str) -> int:
    """Schat tokens via word count * 1.3."""
    if not text:
        return 0
    words = len((text or "").strip().split())
    return int(words * 1.3)


class KnowledgeService:
    """Service voor retrieval van knowledge chunks voor agents."""

    def __init__(self, pool=None):
        """pool: asyncpg pool. Als None, wordt get_db() aangeroepen bij retrieve."""
        self._pool = pool

    async def _get_pool(self):
        if self._pool is not None:
            return self._pool
        return await get_db()

    async def _is_blocked(
        self,
        conn,
        agent_id: str,
        document_id: Optional[Any],
        client_slug: Optional[str] = None,
    ) -> bool:
        """
        Controleer in volgorde: doc-specifiek → client → agency.
        Return True als op enig niveau permission_level='none' gevonden.
        Geen regel op alle niveaus = default read (return False).
        """
        # 1. Document-specifiek
        if document_id is not None:
            r = await conn.fetchval(
                """
                SELECT 1 FROM knowledge_permissions
                WHERE agent_id = $1 AND document_id = $2 AND permission_level = 'none'
                LIMIT 1
                """,
                agent_id,
                document_id,
            )
            if r:
                return True

        # 2. Client-specifiek
        if client_slug is not None:
            r = await conn.fetchval(
                """
                SELECT 1 FROM knowledge_permissions
                WHERE agent_id = $1 AND document_id IS NULL AND client_slug = $2
                  AND permission_level = 'none'
                LIMIT 1
                """,
                agent_id,
                client_slug,
            )
            if r:
                return True

        # 3. Agency-wide
        r = await conn.fetchval(
            """
            SELECT 1 FROM knowledge_permissions
            WHERE agent_id = $1 AND document_id IS NULL AND client_slug IS NULL
              AND permission_level = 'none'
            LIMIT 1
            """,
            agent_id,
        )
        return bool(r)

    async def retrieve_for_agent(
        self,
        agent_id: str,
        query: str,
        domain: Optional[str] = None,
        client_slug: Optional[str] = None,
        client_context_mode: str = "optional",
        top_k: int = 8,
    ) -> dict[str, Any]:
        """
        Haalt relevante chunks op voor een agent.
        Agency-wide en client_context worden apart opgehaald en gecombineerd.
        Returns dict with chunks, client_context, lessons, lessons_text, total_lessons.
        """
        pool = await self._get_pool()
        query_embedding = await generate_embedding((query or "")[:8000])
        embedding_json = json.dumps(query_embedding)

        async with pool.acquire() as conn:
            if domain:
                agency_rows = await conn.fetch(
                    """
                    SELECT kc.chunk_text, kc.chunk_index,
                           kd.document_id, kd.title, kd.doc_type, kd.domain,
                           kd.access_level, kd.client_slug,
                           1 - (kc.embedding <=> $1::vector) AS similarity
                    FROM knowledge_chunks kc
                    JOIN knowledge_documents kd ON kd.document_id = kc.document_id
                    WHERE kd.client_slug IS NULL
                      AND kd.doc_type != 'client_context'
                      AND kd.status = 'approved'
                      AND kd.access_level != 'restricted'
                      AND kc.is_active = true
                      AND kc.embedding IS NOT NULL
                      AND kd.domain = $3
                    ORDER BY kc.embedding <=> $1::vector
                    LIMIT $2
                    """,
                    embedding_json,
                    top_k * 2,
                    domain,
                )
            else:
                agency_rows = await conn.fetch(
                    """
                    SELECT kc.chunk_text, kc.chunk_index,
                           kd.document_id, kd.title, kd.doc_type, kd.domain,
                           kd.access_level, kd.client_slug,
                           1 - (kc.embedding <=> $1::vector) AS similarity
                    FROM knowledge_chunks kc
                    JOIN knowledge_documents kd ON kd.document_id = kc.document_id
                    WHERE kd.client_slug IS NULL
                      AND kd.doc_type != 'client_context'
                      AND kd.status = 'approved'
                      AND kd.access_level != 'restricted'
                      AND kc.is_active = true
                      AND kc.embedding IS NOT NULL
                    ORDER BY kc.embedding <=> $1::vector
                    LIMIT $2
                    """,
                    embedding_json,
                    top_k * 2,
                )

            agency_chunks = []
            blocked_docs: set[tuple[Optional[Any], Optional[str]]] = set()
            for r in agency_rows:
                doc_id = r["document_id"]
                client_slug_val = r["client_slug"]
                key = (doc_id, client_slug_val)
                if key in blocked_docs:
                    continue
                if await self._is_blocked(conn, agent_id, doc_id, client_slug_val):
                    blocked_docs.add(key)
                    continue
                agency_chunks.append({
                    "chunk_text": r["chunk_text"],
                    "document_id": r.get("document_id"),
                    "title": r.get("title") or "",
                    "doc_type": r["doc_type"] or "sop",
                    "domain": r.get("domain"),
                    "access_level": r["access_level"] or "reference",
                    "similarity": float(r["similarity"]),
                })

        client_chunks: list[dict[str, Any]] = []
        if client_context_mode != "forbidden" and client_slug:
            client_chunks_raw = await self._fetch_client_context(
                pool, client_slug, query_embedding, top_k=3
            )
            async with pool.acquire() as conn:
                for c in client_chunks_raw:
                    doc_id = c.get("document_id")
                    slug_val = c.get("client_slug", client_slug)
                    if await self._is_blocked(conn, agent_id, doc_id, slug_val):
                        continue
                    client_chunks.append({
                        "chunk_text": c["chunk_text"],
                        "document_id": c.get("document_id"),
                        "title": "",
                        "doc_type": "client_context",
                        "domain": None,
                        "access_level": "approved",
                        "similarity": c["similarity"],
                    })

        combined = agency_chunks + client_chunks
        reranked = self._rerank_by_priority(combined)
        chunks = self._apply_token_budget(reranked)

        from app.services.lessons_retriever import LessonsRetriever

        retriever = LessonsRetriever()
        lessons = await retriever.retrieve(
            pool=pool, query=query, domain=domain, agent_id=agent_id, top_k=3,
        )
        lessons_text = retriever.format_for_context(lessons) if lessons else ""

        return {
            "chunks": chunks,
            "client_context": [c["chunk_text"] for c in client_chunks],
            "lessons": lessons,
            "lessons_text": lessons_text,
            "total_lessons": len(lessons),
        }

    async def _fetch_client_context(
        self,
        pool,
        client_slug: str,
        query_embedding: list[float],
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Haalt client_context chunks op — APART van agency-wide.
        NOOIT mengen met agency-wide query.
        """
        embedding_json = json.dumps(query_embedding)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT kc.chunk_text, kd.document_id, kd.client_slug,
                       1 - (kc.embedding <=> $1::vector) AS similarity
                FROM knowledge_chunks kc
                JOIN knowledge_documents kd ON kd.document_id = kc.document_id
                WHERE kd.doc_type = 'client_context'
                  AND kd.client_slug = $2
                  AND kd.status = 'approved'
                  AND kc.is_active = true
                  AND kc.embedding IS NOT NULL
                ORDER BY kc.embedding <=> $1::vector
                LIMIT $3
                """,
                embedding_json,
                client_slug,
                top_k,
            )
        return [
            {
                "chunk_text": r["chunk_text"],
                "document_id": r["document_id"],
                "client_slug": r["client_slug"],
                "similarity": float(r["similarity"]),
            }
            for r in rows
        ]

    def _rerank_by_priority(
        self, chunks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Sorteer op PRIORITY_ORDER, binnen dezelfde prioriteit op similarity DESC.
        """
        priority_map = {
            (dt, al): i for i, (dt, al) in enumerate(PRIORITY_ORDER)
        }

        def sort_key(c: dict) -> tuple[int, float]:
            dt = c.get("doc_type") or "sop"
            al = c.get("access_level") or "reference"
            prio = priority_map.get((dt, al), len(PRIORITY_ORDER))
            sim = c.get("similarity", 0.0)
            return (prio, -sim)

        return sorted(chunks, key=sort_key)

    def _apply_token_budget(
        self, chunks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Truncate per doc_type volgens budget. Totaal max 6000 tokens.
        Returns list of chunk dicts (chunk_text, document_id, title, doc_type, domain, similarity).
        """
        budget_used_by_type: dict[str, int] = {}
        total_used = 0
        result: list[dict[str, Any]] = []

        for c in chunks:
            chunk_text = c.get("chunk_text", "")
            doc_type = c.get("doc_type") or "sop"
            budget = TOKEN_BUDGET_BY_TYPE.get(
                doc_type, TOKEN_BUDGET_DEFAULT
            )
            used = budget_used_by_type.get(doc_type, 0)
            remaining_type = max(0, budget - used)
            remaining_total = max(0, TOKEN_BUDGET_TOTAL_MAX - total_used)
            cap = min(remaining_type, remaining_total)

            if cap <= 0:
                continue

            tokens = _estimate_tokens(chunk_text)
            if tokens <= cap:
                text_used = chunk_text
                tokens_used = tokens
            else:
                words = chunk_text.split()
                take_words = int(cap / 1.3)
                text_used = " ".join(words[:take_words]) if take_words else ""
                tokens_used = cap

            if text_used.strip():
                result.append({
                    "chunk_text": text_used,
                    "document_id": c.get("document_id"),
                    "title": c.get("title") or "",
                    "doc_type": doc_type,
                    "domain": c.get("domain"),
                    "similarity": c.get("similarity", 0.0),
                })
                budget_used_by_type[doc_type] = used + tokens_used
                total_used += tokens_used

            if total_used >= TOKEN_BUDGET_TOTAL_MAX:
                break

        return result
