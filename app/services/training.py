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

import httpx
from bs4 import BeautifulSoup
import tiktoken
import openai

logger = logging.getLogger(__name__)


class TrainingError(Exception):
    """Raised when training fails due to validation or processing errors."""


_ENCODING = None
_OPENAI_CLIENT: Optional[openai.AsyncOpenAI] = None


def _get_encoding():
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def _get_openai_client() -> openai.AsyncOpenAI:
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = openai.AsyncOpenAI()
    return _OPENAI_CLIENT


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
    """Split text into overlapping token chunks.

    Returns list of (chunk_text, start_token_index).
    """
    if chunk_size <= 0:
        raise TrainingError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise TrainingError("overlap must be >= 0 and < chunk_size")

    clean_text = re.sub(r"\s+", " ", text or "").strip()
    if not clean_text:
        return []

    encoding = _get_encoding()
    tokens = encoding.encode(clean_text)
    if not tokens:
        return []

    chunks: List[Tuple[str, int]] = []
    step = chunk_size - overlap

    for start in range(0, len(tokens), step):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk = encoding.decode(chunk_tokens).strip()
        if chunk:
            chunks.append((chunk, start))
        if end >= len(tokens):
            break

    return chunks


async def generate_embedding(text: str) -> List[float]:
    """Generate an embedding for a given text using OpenAI."""
    if not text:
        raise TrainingError("Cannot embed empty text")

    try:
        client = _get_openai_client()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
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
        for idx, (chunk_text, _start_token) in enumerate(chunks):
            embedding = None
            if include_embedding:
                embedding = await generate_embedding(chunk_text)

            insert_cols = ["agent_id", "source_url", "chunk_text"]
            values = [agent_id, source_url, chunk_text]

            if include_chunk_index:
                insert_cols.append("chunk_index")
                values.append(idx)

            if include_embedding:
                insert_cols.append("embedding")
                values.append(embedding)

            if include_is_active:
                insert_cols.append("is_active")
                values.append(True)

            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
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
        if "knowledge_base_sources" not in columns:
            return

        current_sources = await conn.fetchval(
            "SELECT knowledge_base_sources FROM hired_agents WHERE agent_id = $1",
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
            }
        )

        await conn.execute(
            """
            UPDATE hired_agents
            SET knowledge_base_sources = $1, updated_at = NOW()
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
        "source_url": validated,
        "chunks_stored": chunks_stored,
        "status": "trained",
        "approved_by": approved_by,
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
