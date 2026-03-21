"""
Google Natural Language API adapter.
Sentimentanalyse, entity-extractie en inhoudsclassificatie voor copy-review.
Activeren: zet GOOGLE_NL_API_KEY in systemd override.
"""
import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_NL_API_KEY", "")
BASE_URL = "https://language.googleapis.com/v1"
ENABLED = bool(API_KEY)


def _doc(text: str) -> dict:
    return {"document": {"type": "PLAIN_TEXT", "content": text}}


async def analyze_sentiment(text: str) -> dict:
    """Sentimentanalyse: score (-1 tot 1) en magnitude."""
    if not ENABLED:
        return {"enabled": False, "data": None}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{BASE_URL}/documents:analyzeSentiment?key={API_KEY}",
                json=_doc(text),
            )
            resp.raise_for_status()
            raw = resp.json()
        sentiment = raw.get("documentSentiment", {})
        return {
            "enabled": True,
            "data": {
                "score": sentiment.get("score"),
                "magnitude": sentiment.get("magnitude"),
                "sentences": [
                    {
                        "text": s.get("text", {}).get("content"),
                        "score": s.get("sentiment", {}).get("score"),
                    }
                    for s in raw.get("sentences", [])
                ],
            },
        }
    except Exception as e:
        logger.error("NL sentiment fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def analyze_entities(text: str) -> dict:
    """Entity-extractie: welke entiteiten worden benoemd en hoe prominent."""
    if not ENABLED:
        return {"enabled": False, "data": None}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{BASE_URL}/documents:analyzeEntities?key={API_KEY}",
                json=_doc(text),
            )
            resp.raise_for_status()
            raw = resp.json()
        return {
            "enabled": True,
            "data": {
                "entities": [
                    {
                        "name": e.get("name"),
                        "type": e.get("type"),
                        "salience": round(e.get("salience", 0), 4),
                    }
                    for e in raw.get("entities", [])
                ]
            },
        }
    except Exception as e:
        logger.error("NL entities fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def classify_text(text: str) -> dict:
    """Inhoudsclassificatie: contentkategorieën met confidence score."""
    if not ENABLED:
        return {"enabled": False, "data": None}
    if len(text.split()) < 20:
        return {"enabled": True, "data": None, "error": "text_too_short"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{BASE_URL}/documents:classifyText?key={API_KEY}",
                json=_doc(text),
            )
            resp.raise_for_status()
            raw = resp.json()
        return {
            "enabled": True,
            "data": {
                "categories": [
                    {
                        "name": c.get("name"),
                        "confidence": round(c.get("confidence", 0), 4),
                    }
                    for c in raw.get("categories", [])
                ]
            },
        }
    except Exception as e:
        logger.error("NL classify fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def full_analysis(text: str) -> dict:
    """Voert sentiment + entities + classify parallel uit. Entry point voor QA Reviewer."""
    sentiment, entities, classification = await asyncio.gather(
        analyze_sentiment(text),
        analyze_entities(text),
        classify_text(text),
    )
    return {
        "enabled": ENABLED,
        "sentiment": sentiment.get("data"),
        "entities": entities.get("data"),
        "classification": classification.get("data"),
    }
