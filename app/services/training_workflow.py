"""
app/services/training_workflow.py
Training Workflow — Crew Intelligent
Spec: Product Spec v1.1, Sectie 5

Stack: asyncpg, httpx (follow_redirects), BeautifulSoup, BGE-M3 (local)
Embeddings: BAAI/bge-m3 (1024 dimensies), lazy-loaded
Kolom: knowledge_base_sources (niet knowledge_sources)
"""

import json
from datetime import datetime, timezone
from typing import Optional

import httpx
import asyncpg

from app.services.training import (
    validate_url,
    chunk_text as _chunk_text_legacy,
    generate_embedding,
    update_knowledge_sources,
    TrainingError,
)

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Splitst tekst in overlappende chunks. Returns list[str]."""
    chunks_tuples = _chunk_text_legacy(text, chunk_size=chunk_size, overlap=overlap)
    return [c[0] for c in chunks_tuples]


async def _scrape(url: str) -> Optional[str]:
    """Fetch URL en extraheer leesbare tekst."""
    import os
    validated = validate_url(url)
    verify = os.getenv("TRAINING_SSL_VERIFY", "true").lower() != "false"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, verify=verify) as client:
            response = await client.get(
                validated,
                headers={"User-Agent": "CrewIntelligent/1.0"},
            )
            response.raise_for_status()
            html = response.text
    except Exception as e:
        raise TrainingError(f"Scrape mislukt voor {url}: {e}") from e

    if BS4_AVAILABLE:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    import re
    return re.sub(r"<[^>]+>", " ", html)


class TrainingWorkflow:
    """Training Workflow class — scrape, chunk, embed, store. Spec v1.1 Sectie 5."""

    def __init__(self, pool: asyncpg.pool.Pool):
        self.pool = pool

    async def start_training(
        self,
        agent_id: str,
        url: str,
        approved_by: str = "ceo",
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> dict:
        """
        Volledige training flow: scrape URL, chunk, embed, sla op.
        Update knowledge_base_sources in hired_agents.
        Returns: {chunks_processed, agent_id, source_url}
        """
        text = await _scrape(url)
        if not text or len(text) < 50:
            raise TrainingError(f"Kon geen tekst ophalen van {url} of te kort")

        chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            raise TrainingError("Geen chunks gegenereerd — pagina mogelijk leeg")

        processed = 0
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_knowledge SET is_active = false
                WHERE agent_id = $1 AND source_url = $2
                """,
                agent_id,
                url,
            )

            for i, chunk in enumerate(chunks):
                embedding = await generate_embedding(chunk[:8000])
                await conn.execute(
                    """
                    INSERT INTO agent_knowledge
                        (agent_id, source_url, chunk_text, embedding, chunk_index, is_active)
                    VALUES ($1, $2, $3, $4::vector, $5, true)
                    """,
                    agent_id,
                    url,
                    chunk,
                    json.dumps(embedding),
                    i,
                )
                processed += 1

        await update_knowledge_sources(
            self.pool,
            agent_id,
            url,
            processed,
            approved_by=approved_by,
        )

        return {
            "chunks_processed": processed,
            "agent_id": agent_id,
            "source_url": url,
        }

    async def retrieve_context(
        self,
        agent_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[str]:
        """Haalt de meest relevante chunks op via cosine similarity (<=>, is_active=true)."""
        query_embedding = await generate_embedding(query[:8000])
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chunk_text
                FROM agent_knowledge
                WHERE agent_id = $1 AND is_active = true AND embedding IS NOT NULL
                ORDER BY embedding <=> $2::vector
                LIMIT $3
                """,
                agent_id,
                json.dumps(query_embedding),
                top_k,
            )
        return [row["chunk_text"] for row in rows]


async def retrieve_agent_context(
    agent_id: str,
    query: str,
    pool: asyncpg.pool.Pool,
    top_k: int = 5,
) -> str:
    """
    Haalt de meest relevante kennischunks op voor een agent op basis van de query.
    Retourneert een geformatteerde string klaar voor prompt-injectie.
    Geeft lege string terug als er geen kennis is voor de agent.
    """
    if not query or not agent_id:
        return ""
    try:
        query_embedding = await generate_embedding((query or "")[:8000])
    except Exception:
        return ""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chunk_text, source_url, chunk_index
            FROM agent_knowledge
            WHERE agent_id = $1 AND is_active = true AND embedding IS NOT NULL
            ORDER BY embedding <=> $2::vector
            LIMIT $3
            """,
            agent_id,
            json.dumps(query_embedding),
            top_k,
        )
    if not rows:
        return ""
    parts = ["=== Relevante kennisbronnen ==="]
    for row in rows:
        url = row.get("source_url") or ""
        idx = row.get("chunk_index", 0)
        text = (row.get("chunk_text") or "").strip()
        parts.append(f"[Bron: {url}, chunk {idx}]")
        parts.append(text)
        parts.append("")
    parts.append("===")
    return "\n".join(parts)
