"""Knowledge Context Builder — prepares knowledge for injection into agent prompts.

Fetches chunks + lessons via KnowledgeService.retrieve_for_agent() and formats
them as a prompt block. Also provides log_knowledge_usage() for audit trail.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_CHUNK_TOKENS = 4000


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return int(len(text.strip().split()) * 1.3)


class KnowledgeContextBuilder:

    async def build(
        self,
        pool,
        agent_id: str,
        query: str,
        domain: Optional[str] = None,
        client_slug: Optional[str] = None,
        client_context_mode: str = "optional",
    ) -> dict[str, Any]:
        from app.services.knowledge_service import KnowledgeService

        svc = KnowledgeService(pool=pool)
        result = await svc.retrieve_for_agent(
            agent_id=agent_id,
            query=query,
            domain=domain,
            client_slug=client_slug,
            client_context_mode=client_context_mode,
        )

        chunks = result.get("chunks", [])
        lessons_text = result.get("lessons_text", "")
        lessons = result.get("lessons", [])

        sources_used: list[dict[str, str]] = []
        for chunk_text in chunks:
            sources_used.append({"type": "chunk", "text_preview": chunk_text[:80]})
        for lesson in lessons:
            sources_used.append({
                "type": "lesson",
                "lesson_id": lesson.get("lesson_id", ""),
                "title": lesson.get("title", ""),
            })

        chunks_block = self._format_chunks(chunks)
        parts: list[str] = []
        if chunks_block:
            parts.append(f"## Relevante Kennis\n\n{chunks_block}")
        if lessons_text:
            parts.append(f"## Lessons uit de praktijk\n\n{lessons_text}")

        prompt_block = "\n\n".join(parts) if parts else ""

        total_chunks = len(chunks)
        total_lessons = result.get("total_lessons", 0)

        if prompt_block:
            logger.info(
                "[KNOWLEDGE] agent=%s: %d chunks, %d lessons geïnjecteerd",
                agent_id, total_chunks, total_lessons,
            )

        return {
            "prompt_block": prompt_block,
            "sources_used": sources_used,
            "total_chunks": total_chunks,
            "total_lessons": total_lessons,
        }

    def _format_chunks(self, chunks: list[str]) -> str:
        parts: list[str] = []
        total_tokens = 0
        for chunk_text in chunks:
            tokens = _estimate_tokens(chunk_text)
            if total_tokens + tokens > MAX_CHUNK_TOKENS:
                break
            parts.append(chunk_text)
            total_tokens += tokens
        return "\n\n---\n\n".join(parts)


async def log_knowledge_usage(
    pool,
    job_id: Optional[str],
    step_id: Optional[str],
    agent_id: str,
    sources: list[dict[str, str]],
) -> None:
    """Write a row to knowledge_usage_log for audit purposes."""
    document_ids = []
    lesson_ids = []
    for s in sources:
        if s.get("type") == "chunk" and s.get("document_id"):
            document_ids.append(s["document_id"])
        elif s.get("type") == "lesson" and s.get("lesson_id"):
            lesson_ids.append(s["lesson_id"])

    chunks_used = sum(1 for s in sources if s.get("type") == "chunk")
    lessons_used = sum(1 for s in sources if s.get("type") == "lesson")

    if chunks_used == 0 and lessons_used == 0:
        return

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO knowledge_usage_log
                    (job_id, step_id, agent_id, document_ids, lesson_ids, chunks_used, lessons_used)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
                """,
                job_id,
                step_id,
                agent_id,
                document_ids or [],
                lesson_ids or [],
                chunks_used,
                lessons_used,
            )
    except Exception:
        logger.warning("Failed to log knowledge usage for job=%s", job_id, exc_info=True)
