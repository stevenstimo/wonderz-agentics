"""Parse @client mentions from text and resolve to validated client_slug for a user."""

import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Match @word (slug: lowercase letters, numbers, underscores)
MENTION_PATTERN = re.compile(r"@([a-z0-9_]+)", re.IGNORECASE)


def parse_mention_slugs(text: str) -> List[str]:
    """Extract unique @mention slugs from text, normalized to lowercase."""
    if not text or not isinstance(text, str):
        return []
    slugs = []
    seen = set()
    for m in MENTION_PATTERN.finditer(text):
        slug = (m.group(1) or "").strip().lower()
        if slug and slug not in seen:
            seen.add(slug)
            slugs.append(slug)
    return slugs


async def resolve_client_slug(pool, user_id: str, slug: str) -> Optional[str]:
    """
    Check that slug exists in clients for this user_id.
    Returns the slug if valid, else None.
    """
    if not pool or not user_id or not slug:
        return None
    slug_clean = (slug or "").strip().lower()
    if not slug_clean:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT slug FROM clients WHERE user_id = $1 AND slug = $2 AND (is_active IS NULL OR is_active = true)",
                user_id,
                slug_clean,
            )
            if row:
                return row["slug"]
    except Exception as e:
        logger.warning("resolve_client_slug failed for user_id=%s slug=%s: %s", user_id, slug_clean, e)
    return None


async def resolve_first_mention(pool, user_id: str, text: str) -> Optional[str]:
    """
    Parse text for @mentions, validate first one against user's clients.
    Returns client_slug if found and valid, else None.
    """
    slugs = parse_mention_slugs(text or "")
    for slug in slugs:
        resolved = await resolve_client_slug(pool, user_id, slug)
        if resolved:
            return resolved
    return None
