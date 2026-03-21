"""
Content kwaliteitsfilter voor gescrapete tekst.

Twee lagen:
1. Heuristiek-filter: snelle blacklist-check, geen LLM
2. AI-filter: Claude Haiku kwaliteitscheck per chunk (optioneel, duurder)
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Laag 1: Heuristiek-filter
# ─────────────────────────────────────────────

_GARBAGE_TERMS = [
    "sign in to view",
    "agree & join",
    "forgot password",
    "create an account",
    "create a free account",
    "log in to continue",
    "please log in",
    "you must be logged in",
    "cookie policy",
    "privacy policy",
    "terms of service",
    "all rights reserved",
    "subscribe to read",
    "sign up for free",
    "join now",
    "continue with google",
    "continue with facebook",
    "skip to main content",
    "back to top",
    "share this article",
    "follow us on",
]

_MIN_WORDS = 20


def _extract_anthropic_text(content: Any) -> str:
    if not content:
        return ""
    parts = []
    for block in content:
        if hasattr(block, "text") and block.text is not None:
            parts.append(str(block.text))
    return "".join(parts).strip()


def is_garbage(text: str) -> bool:
    """
    Snelle heuristiek check. Goedkoop, geen LLM.
    Geeft True terug als de tekst hoogstwaarschijnlijk ruis is.
    """
    if not text or not text.strip():
        return True

    lower = text.lower()

    for term in _GARBAGE_TERMS:
        if term in lower:
            logger.debug("[FILTER] Garbage term gevonden: '%s'", term)
            return True

    word_count = len(text.split())
    if word_count < _MIN_WORDS:
        logger.debug("[FILTER] Te weinig woorden: %s < %s", word_count, _MIN_WORDS)
        return True

    if len(text) > 0:
        special_chars = len(re.findall(r"[|>/\\]", text))
        if special_chars > len(text) * 0.05:
            logger.debug("[FILTER] Te veel speciale tekens: %s", special_chars)
            return True

    return False


def filter_chunks_heuristic(chunks: list[str]) -> list[str]:
    """Filtert een lijst van chunks met de heuristiek-filter."""
    before = len(chunks)
    filtered = [c for c in chunks if not is_garbage(c)]
    after = len(filtered)

    if before != after:
        logger.info("[FILTER] Heuristiek: %s chunks verwijderd (%s → %s)", before - after, before, after)

    return filtered


# ─────────────────────────────────────────────
# Laag 2: Claude Haiku kwaliteitsfilter
# ─────────────────────────────────────────────

_DEFAULT_HAIKU_MODEL = os.getenv("CONTENT_FILTER_AI_MODEL", "claude-3-5-haiku-20241022")


async def filter_chunks_ai(
    chunks: list[str],
    context_hint: str = "",
    use_ai: bool = True,
) -> list[str]:
    """
    Filtert chunks met Claude Haiku als kwaliteitscheck.
    Alleen aanroepen na filter_chunks_heuristic om kosten te beperken.
    """
    if not use_ai or not chunks:
        return chunks

    try:
        from anthropic import AsyncAnthropic
    except Exception as e:
        logger.warning("[FILTER] Anthropic niet beschikbaar: %s", e)
        return chunks

    client = AsyncAnthropic()
    good_chunks: list[str] = []

    for i, chunk in enumerate(chunks):
        try:
            if context_hint.strip():
                q = (
                    "Is de volgende tekst bruikbare professionele inhoud over "
                    f"{context_hint.strip()}? Antwoord alleen met JA of NEE.\n\n"
                    f"Tekst:\n{chunk[:500]}"
                )
            else:
                q = (
                    "Is de volgende tekst bruikbare professionele inhoud? "
                    "Antwoord alleen met JA of NEE.\n\n"
                    f"Tekst:\n{chunk[:500]}"
                )
            response = await client.messages.create(
                model=_DEFAULT_HAIKU_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": q}],
            )
            answer = _extract_anthropic_text(response.content).upper()

            if "JA" in answer:
                good_chunks.append(chunk)
            else:
                logger.debug("[FILTER] AI: chunk %s afgekeurd", i + 1)

        except Exception as e:
            logger.warning("[FILTER] AI check gefaald voor chunk %s: %s", i + 1, e)
            good_chunks.append(chunk)

    removed = len(chunks) - len(good_chunks)
    if removed > 0:
        logger.info("[FILTER] AI: %s chunks verwijderd (%s → %s)", removed, len(chunks), len(good_chunks))

    return good_chunks


async def filter_chunks(
    chunks: list[str],
    context_hint: str = "",
    use_ai_filter: bool = False,
) -> list[str]:
    """
    Hoofdfunctie: heuristiek altijd, AI optioneel.
    use_ai_filter=False by default om kosten te beheersen.
    """
    chunks = filter_chunks_heuristic(chunks)

    if use_ai_filter:
        chunks = await filter_chunks_ai(chunks, context_hint=context_hint, use_ai=True)

    return chunks
