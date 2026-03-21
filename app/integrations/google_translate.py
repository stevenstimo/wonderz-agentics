"""
Google Translate API adapter.
Vertaalt content naar doeltaal.
Activeren: zet GOOGLE_TRANSLATE_API_KEY in systemd override.
LET OP: betaald per karakter (~$20 per 1M tekens). Altijd bewust aanroepen.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
BASE_URL = "https://translation.googleapis.com/language/translate/v2"
ENABLED = bool(API_KEY)


async def translate(text: str, target_language: str, source_language: str | None = None) -> dict:
    """
    Vertaalt tekst naar target_language (bijv. 'nl', 'en', 'de').
    source_language optioneel — wordt auto-gedetecteerd als leeg.
    """
    if not ENABLED:
        return {"enabled": False, "data": None}

    payload = {
        "q": text,
        "target": target_language,
        "format": "text",
        "key": API_KEY,
    }
    if source_language:
        payload["source"] = source_language

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(BASE_URL, json=payload)
            resp.raise_for_status()
            raw = resp.json()

        translated = raw.get("data", {}).get("translations", [{}])[0]
        return {
            "enabled": True,
            "data": {
                "translated_text": translated.get("translatedText"),
                "detected_source_language": translated.get("detectedSourceLanguage"),
                "target_language": target_language,
                "char_count": len(text),
            },
        }
    except Exception as e:
        logger.error("Translate API fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}
