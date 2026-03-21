"""
Google Knowledge Graph API adapter.
Entiteitsdata over merken, personen en bedrijven.
Activeren: zet GOOGLE_KNOWLEDGE_GRAPH_API_KEY in systemd override.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_KNOWLEDGE_GRAPH_API_KEY", "")
BASE_URL = "https://kgsearch.googleapis.com/v1/entities:search"
ENABLED = bool(API_KEY)


async def search_entity(query: str, limit: int = 5) -> dict:
    if not ENABLED:
        return {"enabled": False, "data": None}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                BASE_URL,
                params={"query": query, "limit": limit, "key": API_KEY, "indent": True},
            )
            resp.raise_for_status()
            raw = resp.json()

        items = raw.get("itemListElement", [])
        return {
            "enabled": True,
            "data": {
                "entities": [
                    {
                        "name": item.get("result", {}).get("name"),
                        "description": item.get("result", {}).get("description"),
                        "types": item.get("result", {}).get("@type", []),
                        "score": item.get("resultScore"),
                        "url": item.get("result", {}).get("url"),
                    }
                    for item in items
                ]
            },
        }
    except Exception as e:
        logger.error("Knowledge Graph fout voor '%s': %s", query, e)
        return {"enabled": True, "data": None, "error": str(e)}
