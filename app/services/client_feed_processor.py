"""
Client product feed processor: download XML, split by tag, one chunk per product; embed and store.
"""
import json
import logging
from xml.etree import ElementTree as ET

import httpx

from app.services.training import generate_embedding

logger = logging.getLogger(__name__)

USER_AGENT = "WonderzBot/1.0"
MAX_PRODUCTS = 10_000


class ClientFeedProcessor:
    def __init__(self, client_id: str, datasource_id: int, db_pool):  # noqa: ANN001
        self.client_id = client_id
        self.datasource_id = datasource_id
        self.pool = db_pool

    def _tag_local(self, tag: str) -> str:
        """Strip namespace for matching: {http://...}item -> item."""
        if "}" in tag:
            return tag.split("}")[-1]
        return tag

    def _elem_text(self, el: ET.Element) -> str:
        """All text content of element and descendants."""
        return " ".join((t or "").strip() for t in el.itertext()).strip()

    def _product_chunk_text(self, product_el: ET.Element, identifier_tag: str) -> tuple[str, str]:
        """Build chunk text from all child elements; return (chunk_text, source_url for identifier)."""
        parts: list[str] = []
        source_url = ""
        id_local = self._tag_local(identifier_tag) if identifier_tag else ""
        for child in product_el:
            local = self._tag_local(child.tag)
            val = self._elem_text(child)
            if local == id_local:
                source_url = val or ""
            if val:
                parts.append(f"{local}: {val}")
        chunk = "\n".join(parts)
        return chunk, source_url or "unknown"

    async def process(
        self,
        feed_url: str,
        splitting_tag: str,
        identifier_tag: str,
    ) -> dict:
        """Download XML, split by splitting_tag, one chunk per product; embed and store. Returns {products_found, chunks_created}."""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(feed_url, headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()
                xml_bytes = resp.content
        except Exception as e:
            logger.exception("client_feed_processor: fetch failed %s: %s", feed_url, e)
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE client_datasources
                    SET status = 'failed', error_detail = $1, updated_at = now()
                    WHERE id = $2
                    """,
                    str(e),
                    self.datasource_id,
                )
            return {"products_found": 0, "chunks_created": 0, "error": str(e)}

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            logger.exception("client_feed_processor: XML parse error %s: %s", feed_url, e)
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE client_datasources
                    SET status = 'failed', error_detail = $1, updated_at = now()
                    WHERE id = $2
                    """,
                    str(e),
                    self.datasource_id,
                )
            return {"products_found": 0, "chunks_created": 0, "error": str(e)}

        # Find all elements matching splitting tag (e.g. item)
        split_local = self._tag_local(splitting_tag)
        products: list[ET.Element] = []
        for el in root.iter():
            if self._tag_local(el.tag) == split_local:
                products.append(el)
            if len(products) >= MAX_PRODUCTS:
                break

        products_found = len(products)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM client_knowledge WHERE datasource_id = $1",
                self.datasource_id,
            )
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'processing', chunks_created = 0, error_detail = NULL, updated_at = now()
                WHERE id = $1
                """,
                self.datasource_id,
            )

        stored = 0
        for idx, product_el in enumerate(products):
            chunk_text, source_url = self._product_chunk_text(product_el, identifier_tag)
            if not chunk_text.strip():
                continue
            piece = (chunk_text or "")[:8000]
            embedding = await generate_embedding(piece)
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO client_knowledge
                    (client_id, datasource_id, source_url, page_title, chunk_text, embedding, chunk_index, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6::vector, $7, true)
                    """,
                    self.client_id,
                    self.datasource_id,
                    source_url,
                    source_url,
                    chunk_text,
                    json.dumps(embedding),
                    idx,
                )
            stored += 1

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'done', chunks_created = $1, finished_at = now(), updated_at = now()
                WHERE id = $2
                """,
                stored,
                self.datasource_id,
            )
        return {"products_found": products_found, "chunks_created": stored}
