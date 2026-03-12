"""Extract @client mentions from chat messages and build context from client integrations."""

import json
import logging
import re

from app.database import get_db

logger = logging.getLogger(__name__)

MENTION_PATTERN = re.compile(r"@([a-zA-Z0-9_-]+)")


async def extract_client_context(message: str, user_id: str) -> str:
    """
    Detect @slug mentions in the message.
    For each found client (for this user), fetch integration metadata and build a context block.
    Returns a formatted context string to prepend to the user message for the agent.
    """
    if not message or not isinstance(message, str):
        return ""
    mentions = MENTION_PATTERN.findall(message)
    if not mentions:
        return ""

    # Normalize and dedupe
    slugs = list(dict.fromkeys((m.strip().lower() for m in mentions if m.strip())))
    if not slugs:
        return ""

    context_blocks: list[str] = []
    pool = await get_db()
    async with pool.acquire() as conn:
        for slug in slugs:
            # Resolve client for this user (case-insensitive slug match)
            client = await conn.fetchrow(
                "SELECT client_id, client_name, slug FROM clients WHERE user_id = $1 AND LOWER(slug) = LOWER($2)",
                user_id,
                slug,
            )
            if not client:
                context_blocks.append(
                    f"[Context voor @{slug}: client niet gevonden voor deze gebruiker.]"
                )
                continue

            canonical_slug = client["slug"]

            # Fetch integrations for this client (user_id + client_slug)
            integrations = await conn.fetch(
                """
                SELECT integration_type, extra_config
                FROM client_integrations
                WHERE user_id = $1 AND client_slug = $2
                """,
                user_id,
                canonical_slug,
            )

            if not integrations:
                context_blocks.append(
                    f"[Context voor @{canonical_slug} ({client['client_name']}): geen actieve integraties gevonden]"
                )
                continue

            lines = [f"[Context voor @{canonical_slug} ({client['client_name']}):"]
            for row in integrations:
                cfg = row["extra_config"]
                if isinstance(cfg, str):
                    try:
                        cfg = json.loads(cfg) if cfg else {}
                    except Exception:
                        cfg = {}
                if not isinstance(cfg, dict):
                    cfg = {}
                itype = row["integration_type"]

                if itype == "ga4" and cfg.get("property_id"):
                    lines.append(f"  GA4 property_id: {cfg['property_id']}")
                elif itype == "google_search_console" and cfg.get("site_url"):
                    lines.append(f"  GSC site_url: {cfg['site_url']}")
                elif itype == "google_ads" and cfg.get("customer_id"):
                    lines.append(f"  Google Ads customer_id: {cfg['customer_id']}")

            lines.append(
                "  De agent kan deze client-data ophalen via de beschikbare tools."
            )
            lines.append("]")
            context_blocks.append("\n".join(lines))

    return "\n\n".join(context_blocks)
