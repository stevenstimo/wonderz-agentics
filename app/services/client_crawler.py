"""
Client website crawler: crawl (follow links) and sitemap modes.
Chunks text, embeds via BGE-M3, stores in client_knowledge.
"""
import asyncio
import json
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.training import chunk_text_by_chars, generate_embedding

logger = logging.getLogger(__name__)

USER_AGENT = "WonderzBot/1.0"
MIN_TEXT_LEN = 100


class ClientCrawler:
    MAX_PAGES = 100
    CHUNK_SIZE = 3200
    CHUNK_OVERLAP = 400

    def __init__(self, client_id: str, datasource_id: int, db_pool):  # noqa: ANN001
        self.client_id = client_id
        self.datasource_id = datasource_id
        self.pool = db_pool

    def _chunk_text(self, text: str) -> list[str]:
        return chunk_text_by_chars(
            text,
            chunk_size=self.CHUNK_SIZE,
            overlap=self.CHUNK_OVERLAP,
        )

    def _normalize_url(self, url: str, base_domain: str) -> str | None:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return None
            host = (parsed.netloc or "").lower().lstrip("www.")
            base_host = base_domain.lower().lstrip("www.")
            if host != base_host and not host.endswith("." + base_host):
                return None
            return urljoin(url, parsed.path or "/")
        except Exception:
            return None

    async def _process_url(self, url: str) -> dict | None:
        """Scrape one page. Returns {title, text} or None."""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            logger.warning("client_crawler: failed to fetch %s: %s", url, e)
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            # Prefer main, article, section; fallback to body if empty or too short
            content_el = soup.find("main") or soup.find("article") or soup.find("section")
            if content_el:
                text = (content_el.get_text(separator="\n", strip=True) or "").strip()
            else:
                text = ""
            if not text or len(text) < MIN_TEXT_LEN:
                body_el = soup.find("body")
                if body_el:
                    text = (body_el.get_text(separator="\n", strip=True) or "").strip()
                else:
                    text = (soup.get_text(separator="\n", strip=True) or "").strip()
            text = re.sub(r"\s+", " ", text).strip()
            logger.info("Page %s: extracted %s chars", url, len(text))
            if len(text) < MIN_TEXT_LEN:
                return None
            title_tag = soup.find("title")
            title = (title_tag.get_text(strip=True) if title_tag else "") or url
            return {"title": title, "text": text}
        except Exception as e:
            logger.warning("client_crawler: parse error %s: %s", url, e)
            return None

    async def _discover_links(self, start_url: str, base_domain: str) -> list[str]:
        """Discover internal links. Max MAX_PAGES unique URLs."""
        seen: set[str] = set()
        to_visit = [start_url]
        base_parsed = urlparse(start_url)
        base_netloc = (base_parsed.netloc or "").lower()

        while to_visit and len(seen) < self.MAX_PAGES:
            url = to_visit.pop(0)
            norm = self._normalize_url(url, base_domain)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            await asyncio.sleep(0.5)
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    resp = await client.get(norm, headers={"User-Agent": USER_AGENT})
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        full = urljoin(norm, href)
                        parsed = urlparse(full)
                        if (parsed.netloc or "").lower() != base_netloc:
                            continue
                        if full not in seen and len(seen) + len(to_visit) < self.MAX_PAGES:
                            to_visit.append(full)
            except Exception as e:
                logger.debug("client_crawler: skip link %s: %s", norm, e)
                continue

        return list(seen)

    async def _parse_sitemap(self, sitemap_url: str) -> list[str]:
        """Read sitemap.xml and return list of URLs."""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(sitemap_url, headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()
                text = resp.text
        except Exception as e:
            logger.warning("client_crawler: sitemap fetch failed %s: %s", sitemap_url, e)
            return []

        urls: list[str] = []
        # Simple extraction of <loc>...</loc>
        for m in re.finditer(r"<loc>\s*([^<]+)\s*</loc>", text, re.IGNORECASE):
            urls.append(m.group(1).strip())
        return urls[: self.MAX_PAGES]

    async def _embed_and_store(
        self,
        chunks: list[str],
        source_url: str,
        page_title: str,
    ) -> int:
        """Insert chunks for this page. Caller must delete existing chunks for datasource once before run."""
        stored = 0
        async with self.pool.acquire() as conn:
            for idx, chunk in enumerate(chunks):
                text = (chunk or "")[:8000]
                if not text.strip():
                    continue
                embedding = await generate_embedding(text)
                await conn.execute(
                    """
                    INSERT INTO client_knowledge
                    (client_id, datasource_id, source_url, page_title, chunk_text, embedding, chunk_index, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6::vector, $7, true)
                    """,
                    self.client_id,
                    self.datasource_id,
                    source_url,
                    page_title,
                    chunk,
                    json.dumps(embedding),
                    idx,
                )
                stored += 1
            return stored

    async def run_crawl(self, domain: str) -> dict:
        """Crawl all internal pages from the root domain."""
        start_url = f"https://{domain}" if not domain.startswith("http") else domain
        parsed = urlparse(start_url)
        base_domain = parsed.netloc or domain

        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM client_knowledge WHERE datasource_id = $1",
                self.datasource_id,
            )
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'processing', pages_found = 0, pages_processed = 0, chunks_created = 0, error_detail = NULL
                WHERE id = $1
                """,
                self.datasource_id,
            )

        urls = await self._discover_links(start_url, base_domain)
        pages_found = len(urls)
        pages_processed = 0
        chunks_created = 0
        pages_skipped_short = 0

        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE client_datasources SET pages_found = $1 WHERE id = $2",
                pages_found,
                self.datasource_id,
            )

        for url in urls:
            await asyncio.sleep(0.5)
            result = await self._process_url(url)
            if not result:
                pages_skipped_short += 1
                continue
            chunks = self._chunk_text(result["text"])
            if not chunks:
                continue
            stored = await self._embed_and_store(chunks, url, result["title"])
            pages_processed += 1
            chunks_created += stored
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE client_datasources
                    SET pages_processed = pages_processed + 1, chunks_created = chunks_created + $2, updated_at = now()
                    WHERE id = $1
                    """,
                    self.datasource_id,
                    stored,
                )

        error_detail = None
        if pages_skipped_short > 0:
            error_detail = f"{pages_skipped_short} pagina's overgeslagen (minder dan 100 tekens)."
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'done', finished_at = now(), updated_at = now(), error_detail = $2
                WHERE id = $1
                """,
                self.datasource_id,
                error_detail,
            )
        return {
            "pages_found": pages_found,
            "pages_processed": pages_processed,
            "chunks_created": chunks_created,
        }

    async def run_sitemap(self, sitemap_url: str) -> dict:
        """Process all URLs from sitemap.xml."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM client_knowledge WHERE datasource_id = $1",
                self.datasource_id,
            )
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'processing', pages_found = 0, pages_processed = 0, chunks_created = 0, error_detail = NULL
                WHERE id = $1
                """,
                self.datasource_id,
            )

        urls = await self._parse_sitemap(sitemap_url)
        pages_found = len(urls)
        pages_processed = 0
        chunks_created = 0
        pages_skipped_short = 0

        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE client_datasources SET pages_found = $1 WHERE id = $2",
                pages_found,
                self.datasource_id,
            )

        for url in urls:
            await asyncio.sleep(0.5)
            result = await self._process_url(url)
            if not result:
                pages_skipped_short += 1
                continue
            chunks = self._chunk_text(result["text"])
            if not chunks:
                continue
            stored = await self._embed_and_store(chunks, url, result["title"])
            pages_processed += 1
            chunks_created += stored
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE client_datasources
                    SET pages_processed = pages_processed + 1, chunks_created = chunks_created + $2, updated_at = now()
                    WHERE id = $1
                    """,
                    self.datasource_id,
                    stored,
                )

        error_detail = None
        if pages_skipped_short > 0:
            error_detail = f"{pages_skipped_short} pagina's overgeslagen (minder dan 100 tekens)."
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'done', finished_at = now(), updated_at = now(), error_detail = $2
                WHERE id = $1
                """,
                self.datasource_id,
                error_detail,
            )
        return {
            "pages_found": pages_found,
            "pages_processed": pages_processed,
            "chunks_created": chunks_created,
        }
