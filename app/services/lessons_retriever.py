"""Lessons Retriever — haalt relevante lessons op voor agent context.

Lessons komen altijd NA kennisdocumenten in de context (PRIORITY_IN_CONTEXT = last).
Ze zijn ondersteunend, nooit leidend.

Search strategy:
  1. Check if lessons table has an embedding column → use cosine similarity
  2. Fallback: PostgreSQL full-text search (dutch config)
  3. Fallback: top_k by confidence_score DESC
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_LESSONS_TOKENS = 1500


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return int(len(text.strip().split()) * 1.3)


class LessonsRetriever:

    PRIORITY_IN_CONTEXT = "last"

    async def retrieve(
        self,
        pool,
        query: str,
        domain: Optional[str] = None,
        agent_id: Optional[str] = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        async with pool.acquire() as conn:
            table_exists = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'lessons'"
            )
            if not table_exists:
                return []

            has_embedding = await conn.fetchval(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'lessons' AND column_name = 'embedding'"
            )

            lessons: list[dict[str, Any]] = []

            if has_embedding:
                lessons = await self._search_by_embedding(conn, query, domain, top_k)
            else:
                lessons = await self._search_by_fts(conn, query, domain, top_k)
                if not lessons:
                    lessons = await self._fallback_by_confidence(conn, domain, top_k)

            if agent_id:
                for lesson in lessons:
                    if lesson.get("agent_id") == agent_id:
                        lesson["confidence_score"] = min(
                            1.0, (lesson.get("confidence_score") or 0) + 0.05
                        )

            lessons.sort(key=lambda x: -(x.get("confidence_score") or 0))
            return lessons[:top_k]

    async def _search_by_embedding(
        self, conn, query: str, domain: Optional[str], top_k: int
    ) -> list[dict[str, Any]]:
        from app.services.training import generate_embedding
        import json

        query_embedding = await generate_embedding((query or "")[:8000])
        embedding_json = json.dumps(query_embedding)

        if domain:
            rows = await conn.fetch(
                """
                SELECT l.lesson_id, l.title, l.gevonden, l.oorzaak, l.fix,
                       l.confidence_score, l.agent_id, l.status,
                       1 - (l.embedding <=> $1::vector) AS similarity
                FROM lessons l
                LEFT JOIN agents a ON l.agent_id = a.agent_id
                WHERE l.status = 'active'
                  AND l.confidence_score >= 0.70
                  AND (a.specialization ILIKE '%' || $3 || '%' OR $3 IS NULL)
                ORDER BY l.embedding <=> $1::vector
                LIMIT $2
                """,
                embedding_json,
                top_k,
                domain,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT l.lesson_id, l.title, l.gevonden, l.oorzaak, l.fix,
                       l.confidence_score, l.agent_id, l.status,
                       1 - (l.embedding <=> $1::vector) AS similarity
                FROM lessons l
                WHERE l.status = 'active'
                  AND l.confidence_score >= 0.70
                ORDER BY l.embedding <=> $1::vector
                LIMIT $2
                """,
                embedding_json,
                top_k,
            )

        return [self._row_to_dict(r) for r in rows]

    async def _search_by_fts(
        self, conn, query: str, domain: Optional[str], top_k: int
    ) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []

        if domain:
            rows = await conn.fetch(
                """
                SELECT l.lesson_id, l.title, l.gevonden, l.oorzaak, l.fix,
                       l.confidence_score, l.agent_id, l.status
                FROM lessons l
                LEFT JOIN agents a ON l.agent_id = a.agent_id
                WHERE l.status = 'active'
                  AND l.confidence_score >= 0.70
                  AND to_tsvector('dutch',
                        COALESCE(l.title,'') || ' ' ||
                        COALESCE(l.gevonden,'') || ' ' ||
                        COALESCE(l.oorzaak,'') || ' ' ||
                        COALESCE(l.fix,'')
                      ) @@ plainto_tsquery('dutch', $1)
                  AND (a.specialization ILIKE '%' || $3 || '%' OR $3 IS NULL)
                ORDER BY l.confidence_score DESC
                LIMIT $2
                """,
                query,
                top_k,
                domain,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT l.lesson_id, l.title, l.gevonden, l.oorzaak, l.fix,
                       l.confidence_score, l.agent_id, l.status
                FROM lessons l
                WHERE l.status = 'active'
                  AND l.confidence_score >= 0.70
                  AND to_tsvector('dutch',
                        COALESCE(l.title,'') || ' ' ||
                        COALESCE(l.gevonden,'') || ' ' ||
                        COALESCE(l.oorzaak,'') || ' ' ||
                        COALESCE(l.fix,'')
                      ) @@ plainto_tsquery('dutch', $1)
                ORDER BY l.confidence_score DESC
                LIMIT $2
                """,
                query,
                top_k,
            )

        return [self._row_to_dict(r) for r in rows]

    async def _fallback_by_confidence(
        self, conn, domain: Optional[str], top_k: int
    ) -> list[dict[str, Any]]:
        if domain:
            rows = await conn.fetch(
                """
                SELECT l.lesson_id, l.title, l.gevonden, l.oorzaak, l.fix,
                       l.confidence_score, l.agent_id, l.status
                FROM lessons l
                LEFT JOIN agents a ON l.agent_id = a.agent_id
                WHERE l.status = 'active'
                  AND l.confidence_score >= 0.70
                  AND (a.specialization ILIKE '%' || $2 || '%' OR $2 IS NULL)
                ORDER BY l.confidence_score DESC, l.created_at DESC
                LIMIT $1
                """,
                top_k,
                domain,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT l.lesson_id, l.title, l.gevonden, l.oorzaak, l.fix,
                       l.confidence_score, l.agent_id, l.status
                FROM lessons l
                WHERE l.status = 'active'
                  AND l.confidence_score >= 0.70
                ORDER BY l.confidence_score DESC, l.created_at DESC
                LIMIT $1
                """,
                top_k,
            )

        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(r) -> dict[str, Any]:
        return {
            "lesson_id": r["lesson_id"],
            "title": r["title"],
            "gevonden": r["gevonden"],
            "oorzaak": r["oorzaak"],
            "fix": r["fix"],
            "confidence_score": float(r["confidence_score"]) if r["confidence_score"] is not None else 0.0,
            "agent_id": r["agent_id"],
            "source": "lessons_store",
        }

    def format_for_context(self, lessons: list[dict[str, Any]]) -> str:
        sorted_lessons = sorted(lessons, key=lambda x: -(x.get("confidence_score") or 0))

        parts: list[str] = []
        total_tokens = 0

        for lesson in sorted_lessons:
            block = (
                f"--- Lesson {lesson['lesson_id']} (confidence: {lesson.get('confidence_score', 0):.2f}) ---\n"
                f"Gevonden: {lesson.get('gevonden', '')}\n"
                f"Oorzaak: {lesson.get('oorzaak', '')}\n"
                f"Fix: {lesson.get('fix', '')}"
            )
            block_tokens = _estimate_tokens(block)
            if total_tokens + block_tokens > MAX_LESSONS_TOKENS:
                break
            parts.append(block)
            total_tokens += block_tokens

        return "\n\n".join(parts)
