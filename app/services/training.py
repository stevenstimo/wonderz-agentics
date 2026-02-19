"""Agent Training Service.

Scrapes URLs, chunks text, and stores knowledge for agents.
Tracks progress in agent_training_sessions table.
"""

import json
import logging
import uuid
import re
from typing import List, Optional, Dict, Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks."""
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence-ending punctuation near the end
            for i in range(min(50, end - start), 0, -1):
                if end - i < len(text) and text[end - i] in '.!?\n':
                    end = end - i + 1
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap
        if start >= len(text):
            break

    return chunks


async def run_training(db_pool, session_id: str, agent_id: str, url: str):
    """Scrape URL, chunk text, store as agent knowledge.

    Updates agent_training_sessions with progress as it processes.
    """
    if not db_pool:
        logger.error(f"Training {session_id}: No DB pool")
        return

    async with db_pool.acquire() as conn:
        try:
            # Mark as processing
            await conn.execute("""
                UPDATE agent_training_sessions
                SET status = 'processing'
                WHERE session_id = $1
            """, session_id)

            # Scrape the URL
            logger.info(f"Training {session_id}: Scraping {url}")
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; WonderzBot/1.0)'
                })
                response.raise_for_status()

            # Parse HTML to text
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()

            text = soup.get_text(separator=' ', strip=True)

            if not text or len(text) < 50:
                raise ValueError(f"Page content too short ({len(text)} chars)")

            # Chunk the text
            chunks = _chunk_text(text, chunk_size=500, overlap=50)
            chunks_total = len(chunks)

            logger.info(f"Training {session_id}: {chunks_total} chunks from {len(text)} chars")

            await conn.execute("""
                UPDATE agent_training_sessions
                SET chunks_total = $1
                WHERE session_id = $2
            """, chunks_total, session_id)

            # Store chunks
            for i, chunk in enumerate(chunks):
                await conn.execute("""
                    INSERT INTO agent_knowledge
                    (agent_id, source_url, chunk_text, chunk_index)
                    VALUES ($1, $2, $3, $4)
                """, agent_id, url, chunk, i)

                # Update progress
                await conn.execute("""
                    UPDATE agent_training_sessions
                    SET chunks_processed = $1
                    WHERE session_id = $2
                """, i + 1, session_id)

            # Mark completed
            await conn.execute("""
                UPDATE agent_training_sessions
                SET status = 'completed', completed_at = NOW()
                WHERE session_id = $1
            """, session_id)

            # Update agent's knowledge_base_sources
            current_sources = await conn.fetchval(
                "SELECT knowledge_base_sources FROM hired_agents WHERE agent_id = $1",
                agent_id
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

            from datetime import datetime
            sources.append({
                "url": url,
                "chunks": chunks_total,
                "added_at": datetime.now().isoformat()
            })

            await conn.execute("""
                UPDATE hired_agents
                SET knowledge_base_sources = $1, updated_at = NOW()
                WHERE agent_id = $2
            """, json.dumps(sources), agent_id)

            logger.info(f"Training {session_id}: Completed — {chunks_total} chunks stored")

        except Exception as e:
            logger.error(f"Training {session_id} failed: {e}")
            await conn.execute("""
                UPDATE agent_training_sessions
                SET status = 'failed', error_message = $1, completed_at = NOW()
                WHERE session_id = $2
            """, str(e)[:1000], session_id)


async def train_agent_from_url(
    pool,
    agent_id: str,
    url: str,
    approved_by: Optional[str] = None
) -> Dict[str, Any]:
    """Create a training session and run training for a given URL."""
    if not pool:
        raise RuntimeError("Database pool not initialized")

    session_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'agent_training_sessions'
        """)
        colset = {c["column_name"] for c in columns}

        insert_cols = ["session_id", "agent_id", "source_url", "status"]
        values = [session_id, agent_id, url, "pending"]

        if approved_by and "approved_by" in colset:
            insert_cols.append("approved_by")
            values.append(approved_by)

        placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
        await conn.execute(
            f"""
                INSERT INTO agent_training_sessions
                ({', '.join(insert_cols)})
                VALUES ({placeholders})
            """,
            *values
        )

    await run_training(pool, session_id, agent_id, url)

    return {
        "session_id": session_id,
        "agent_id": agent_id,
        "status": "training_completed",
        "source_url": url,
    }
