"""
Client text processor: chunk and embed manually entered text; store in client_knowledge.
"""
import json
import logging

from app.services.training import chunk_text_by_chars, generate_embedding

logger = logging.getLogger(__name__)

CHUNK_SIZE = 3200
CHUNK_OVERLAP = 400


class ClientTextProcessor:
    def __init__(self, client_id: str, datasource_id: int, db_pool):  # noqa: ANN001
        self.client_id = client_id
        self.datasource_id = datasource_id
        self.pool = db_pool

    async def process(self, text: str, source_name: str) -> dict:
        """Chunk and embed text, store in client_knowledge. Returns {chunks_created}."""
        clean = (text or "").strip()
        if not clean:
            return {"chunks_created": 0}

        chunks = chunk_text_by_chars(clean, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        if not chunks:
            return {"chunks_created": 0}

        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM client_knowledge WHERE datasource_id = $1",
                self.datasource_id,
            )
            stored = 0
            for idx, chunk in enumerate(chunks):
                piece = (chunk or "")[:8000]
                if not piece.strip():
                    continue
                embedding = await generate_embedding(piece)
                await conn.execute(
                    """
                    INSERT INTO client_knowledge
                    (client_id, datasource_id, source_url, page_title, chunk_text, embedding, chunk_index, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6::vector, $7, true)
                    """,
                    self.client_id,
                    self.datasource_id,
                    source_name,
                    source_name,
                    chunk,
                    json.dumps(embedding),
                    idx,
                )
                stored += 1
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'done', chunks_created = $1, finished_at = now(), updated_at = now(), error_detail = NULL
                WHERE id = $2
                """,
                stored,
                self.datasource_id,
            )
        return {"chunks_created": stored}
