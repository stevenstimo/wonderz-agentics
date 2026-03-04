import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import asyncpg
import json


async def scrape_url(url: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


async def embed_text(text: str, openai_api_key: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {openai_api_key}"},
            json={"input": text, "model": "text-embedding-3-small"},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


async def run_training(agent_id: str, url: str, approved_by: str, db, openai_api_key: str):
    text = await scrape_url(url)
    chunks = chunk_text(text)

    for i, chunk in enumerate(chunks):
        embedding = await embed_text(chunk, openai_api_key)
        await db.execute(
            """
            INSERT INTO agent_knowledge (agent_id, source_url, chunk_text, embedding, chunk_index, created_at, is_active)
            VALUES ($1, $2, $3, $4::vector, $5, $6, true)
        """,
            agent_id,
            url,
            chunk,
            json.dumps(embedding),
            i,
            datetime.now(timezone.utc),
        )

    # Update knowledge_sources in hired_agents
    agent = await db.fetchrow("SELECT knowledge_sources FROM hired_agents WHERE agent_id = $1", agent_id)
    sources = json.loads(agent["knowledge_sources"]) if agent["knowledge_sources"] else []
    sources.append(
        {
            "url": url,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "approved_by": approved_by,
        }
    )
    await db.execute(
        "UPDATE hired_agents SET knowledge_sources = $1 WHERE agent_id = $2",
        json.dumps(sources),
        agent_id,
    )
    return len(chunks)


async def retrieve_context(
    agent_id: str, query: str, db, openai_api_key: str, top_k: int = 5
) -> list[str]:
    embedding = await embed_text(query, openai_api_key)
    rows = await db.fetch(
        """
        SELECT chunk_text FROM agent_knowledge
        WHERE agent_id = $1 AND is_active = true
        ORDER BY embedding <=> $2::vector
        LIMIT $3
    """,
        agent_id,
        json.dumps(embedding),
        top_k,
    )
    return [r["chunk_text"] for r in rows]
