import logging

logger = logging.getLogger(__name__)


async def retrieve_agent_context(pool, agent_id: str, query: str, top_k: int = 3) -> str:
    try:
        import openai

        client = openai.AsyncOpenAI()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        query_embedding = response.data[0].embedding

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chunk_text, source_url
                FROM agent_knowledge
                WHERE agent_id = $1 AND is_active = true
                ORDER BY embedding <=> $2
                LIMIT $3
                """,
                agent_id,
                query_embedding,
                top_k,
            )

        if not rows:
            return ""

        context_parts = []
        for row in rows:
            context_parts.append(f"[From {row['source_url']}]\n{row['chunk_text']}")

        return "\n\n---\n\n".join(context_parts)
    except Exception as e:
        logger.error("Failed to retrieve context: %s", e)
        return ""
