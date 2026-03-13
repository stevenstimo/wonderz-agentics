"""Agent Training Service.

Scrapes URLs, chunks text, generates embeddings, and stores knowledge for agents.
Includes utilities for URL validation, text extraction, and chunking.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any, Optional
from urllib.parse import urlparse

import asyncio
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TrainingError(Exception):
    """Raised when training fails due to validation or processing errors."""


_embedding_model = None


def _get_embedding_model():
    """Lazy-load BGE-M3 to avoid 30s cold start on every backend restart."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("BAAI/bge-m3")
    return _embedding_model


def _embed_sync(text: str) -> List[float]:
    """Sync embedding via BGE-M3. Returns 1024-dim vector."""
    model = _get_embedding_model()
    return model.encode(text, normalize_embeddings=True).tolist()


async def _get_table_columns(conn, table_name: str) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table_name,
    )
    return {row["column_name"] for row in rows}


def validate_url(url: str) -> str:
    """Validate that a URL is HTTP/HTTPS and well-formed."""
    if not url or not isinstance(url, str):
        raise TrainingError("URL is required")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise TrainingError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise TrainingError("URL must include a hostname")

    return url


async def scrape_url(url: str) -> str:
    """Fetch a URL and return raw HTML."""
    validated = validate_url(url)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(
                validated,
                headers={"User-Agent": "Mozilla/5.0 (compatible; WonderzBot/1.0)"},
            )
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as exc:
        raise TrainingError(f"Failed to fetch URL: {exc}") from exc


def extract_text(html: str) -> str:
    """Extract readable text from HTML."""
    soup = BeautifulSoup(html or "", "html.parser")

    for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        element.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Tuple[str, int]]:
    """Split text into overlapping word chunks.

    Returns list of (chunk_text, start_word_index).
    """
    if chunk_size <= 0:
        raise TrainingError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise TrainingError("overlap must be >= 0 and < chunk_size")

    clean_text = re.sub(r"\s+", " ", text or "").strip()
    if not clean_text:
        return []

    words = clean_text.split(" ")
    if not words:
        return []

    chunks: List[Tuple[str, int]] = []
    step = chunk_size - overlap
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words).strip()
        if chunk:
            chunks.append((chunk, start))
        if end >= len(words):
            break
        start += step

    return chunks


def chunk_text_by_chars(
    text: str,
    chunk_size: int = 2000,
    overlap: int = 200,
) -> List[str]:
    """Split text into overlapping character chunks. No tiktoken/OpenAI.

    Each chunk is at most chunk_size chars; last overlap chars of chunk N
    are the first overlap chars of chunk N+1.
    Returns list of chunk strings.
    """
    if chunk_size <= 0:
        raise TrainingError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise TrainingError("overlap must be >= 0 and < chunk_size")

    clean = (text or "").strip()
    if not clean:
        return []

    step = chunk_size - overlap
    start = 0
    chunks: List[str] = []
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunk = clean[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(clean):
            break
        start += step

    return chunks


EMBEDDING_DIM = 1024  # agent_knowledge.embedding vector size (BGE-M3)


async def generate_embedding(text: str) -> List[float]:
    """Generate embedding via local BGE-M3. No API keys required."""
    if not text:
        raise TrainingError("Cannot embed empty text")
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _embed_sync, text)
    except Exception as exc:
        raise TrainingError(f"Embedding generation failed: {exc}") from exc


async def _insert_chunks(
    pool,
    agent_id: str,
    source_url: str,
    chunks: List[Tuple[str, int]],
    progress_callback=None,
) -> int:
    if not pool:
        raise TrainingError("Database pool not initialized")

    if not chunks:
        return 0

    async with pool.acquire() as conn:
        columns = await _get_table_columns(conn, "agent_knowledge")
        include_embedding = "embedding" in columns
        include_chunk_index = "chunk_index" in columns
        include_is_active = "is_active" in columns

        stored = 0
        for idx, (chunk_text, _start_word) in enumerate(chunks):
            embedding = None
            if include_embedding:
                embedding = await generate_embedding(chunk_text)

            insert_cols = ["agent_id", "source_url", "chunk_text"]
            values = [agent_id, source_url, chunk_text]
            placeholder_casts = ["", "", ""]

            if include_chunk_index:
                insert_cols.append("chunk_index")
                values.append(idx)
                placeholder_casts.append("")

            if include_embedding:
                insert_cols.append("embedding")
                values.append(json.dumps(embedding))
                placeholder_casts.append("::vector")

            if include_is_active:
                insert_cols.append("is_active")
                values.append(True)
                placeholder_casts.append("")

            placeholders = ", ".join(
                f"${i}{placeholder_casts[i - 1]}" for i in range(1, len(values) + 1)
            )
            await conn.execute(
                f"""
                INSERT INTO agent_knowledge ({', '.join(insert_cols)})
                VALUES ({placeholders})
                """,
                *values,
            )

            stored += 1
            if progress_callback:
                await progress_callback(conn, stored)

        return stored


async def store_knowledge(pool, agent_id: str, source_url: str, chunks: List[Tuple[str, int]]) -> int:
    """Store chunks and embeddings in the database."""
    return await _insert_chunks(pool, agent_id, source_url, chunks)


async def update_knowledge_sources(
    pool,
    agent_id: str,
    source_url: str,
    chunks_stored: int,
    approved_by: Optional[str] = None,
) -> None:
    if not pool:
        raise TrainingError("Database pool not initialized")

    async with pool.acquire() as conn:
        columns = await _get_table_columns(conn, "hired_agents")
        sources_column = None
        if "knowledge_base_sources" in columns:
            sources_column = "knowledge_base_sources"
        elif "knowledge_sources" in columns:
            sources_column = "knowledge_sources"
        else:
            return

        current_sources = await conn.fetchval(
            f"SELECT {sources_column} FROM hired_agents WHERE agent_id = $1",
            agent_id,
        )

        sources = []
        if current_sources:
            if isinstance(current_sources, str):
                try:
                    sources = json.loads(current_sources)
                except json.JSONDecodeError:
                    sources = []
            elif isinstance(current_sources, list):
                sources = current_sources

        sources = [s for s in sources if s.get("url") != source_url]
        sources.append(
            {
                "url": source_url,
                "chunks": chunks_stored,
                "approved_by": approved_by,
                "added_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",
            }
        )

        update_clause = f"{sources_column} = $1"
        if "updated_at" in columns:
            update_clause = f"{update_clause}, updated_at = NOW()"

        await conn.execute(
            f"""
            UPDATE hired_agents
            SET {update_clause}
            WHERE agent_id = $2
            """,
            json.dumps(sources),
            agent_id,
        )


async def train_agent_from_url(
    pool,
    agent_id: str,
    url: str,
    approved_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Train an agent by scraping a URL and storing embeddings."""
    if not agent_id:
        raise TrainingError("agent_id is required")

    validated = validate_url(url)
    html = await scrape_url(validated)
    text = extract_text(html)

    if len(text) < 50:
        raise TrainingError("Extracted text is too short")

    chunks = chunk_text(text, chunk_size=500, overlap=50)
    if not chunks:
        raise TrainingError("No chunks created from extracted text")

    chunks_stored = await store_knowledge(pool, agent_id, validated, chunks)
    await update_knowledge_sources(pool, agent_id, validated, chunks_stored, approved_by)

    return {
        "agent_id": agent_id,
        "status": "completed",
        "chunks_processed": chunks_stored,
    }


async def run_training(db_pool, session_id: str, agent_id: str, url: str):
    """Background training with session progress updates."""
    if not db_pool:
        logger.error("Training %s: No DB pool", session_id)
        return

    async def _progress(conn, processed: int) -> None:
        await conn.execute(
            """
            UPDATE agent_training_sessions
            SET chunks_processed = $1
            WHERE session_id = $2
            """,
            processed,
            session_id,
        )

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_training_sessions
                SET status = 'processing'
                WHERE session_id = $1
                """,
                session_id,
            )

        html = await scrape_url(url)
        text = extract_text(html)

        if len(text) < 50:
            raise TrainingError("Extracted text is too short")

        chunks = chunk_text(text, chunk_size=500, overlap=50)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_training_sessions
                SET chunks_total = $1
                WHERE session_id = $2
                """,
                len(chunks),
                session_id,
            )

        chunks_stored = await _insert_chunks(db_pool, agent_id, url, chunks, progress_callback=_progress)
        await update_knowledge_sources(db_pool, agent_id, url, chunks_stored)

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_training_sessions
                SET status = 'completed', completed_at = NOW()
                WHERE session_id = $1
                """,
                session_id,
            )

        logger.info("Training %s: Completed — %s chunks stored", session_id, chunks_stored)

    except Exception as exc:
        logger.error("Training %s failed: %s", session_id, exc)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_training_sessions
                SET status = 'failed', error_message = $1, completed_at = NOW()
                WHERE session_id = $2
                """,
                str(exc)[:1000],
                session_id,
            )
