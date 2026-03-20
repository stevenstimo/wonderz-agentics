"""HR Manager Training Resource Discovery.

Zoekt via Anthropic web_search naar relevante trainingsbronnen
en slaat resultaten op als pending training_suggestions.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import asyncpg
import httpx

from app.core.config import DEFAULT_MODEL

logger = logging.getLogger(__name__)


class HRResourceDiscovery:
    """Discovery service voor training resources per development point."""

    async def discover_for_development_point(
        self,
        conn: asyncpg.Connection,
        development_point_id: Any,
        agent_id: str,
        agent_role: str,
        pattern_description: str,
        impact: str,
    ) -> list[dict]:
        """Zoek max 3 bronnen en sla op als pending suggestions."""
        prompt = self._build_search_prompt(agent_role, pattern_description)
        results = await self._search_with_claude(prompt)
        if not results:
            return []

        cols = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'training_suggestions'
            """
        )
        col_set = {r["column_name"] for r in cols}
        if not col_set:
            logger.warning("[HRResourceDiscovery] training_suggestions table not found")
            return []

        created: list[dict] = []
        for item in results[:3]:
            url = str(item.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                continue
            title = str(item.get("title") or "").strip()
            rationale = str(item.get("rationale") or "").strip()[:1000]

            try:
                # Prefer development_point_ref (Opt B / production); Opt A uses development_point_id only.
                if "development_point_ref" in col_set:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO training_suggestions
                          (development_point_ref, agent_id, url, title, rationale, discovered_by, status)
                        SELECT $1, $2, $3, $4, $5, 'hr-manager', 'pending'
                        WHERE NOT EXISTS (
                          SELECT 1 FROM training_suggestions
                          WHERE agent_id = $2 AND url = $3 AND status = 'pending'
                        )
                        RETURNING *
                        """,
                        str(development_point_id),
                        agent_id,
                        url,
                        title,
                        rationale,
                    )
                elif "development_point_id" in col_set:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO training_suggestions
                          (development_point_id, agent_id, url, title, rationale, discovered_by, status)
                        SELECT $1, $2, $3, $4, $5, 'hr-manager', 'pending'
                        WHERE NOT EXISTS (
                          SELECT 1 FROM training_suggestions
                          WHERE agent_id = $2 AND url = $3 AND status = 'pending'
                        )
                        RETURNING *
                        """,
                        development_point_id,
                        agent_id,
                        url,
                        title,
                        rationale,
                    )
                else:
                    logger.warning(
                        "[HRResourceDiscovery] training_suggestions misses development point FK columns"
                    )
                    return created

                if row:
                    created.append(dict(row))
            except Exception as exc:
                logger.warning(
                    "[HRResourceDiscovery] insert failed for point %s (%s): %s",
                    development_point_id,
                    impact,
                    exc,
                )
                continue

        return created

    def _build_search_prompt(self, agent_role: str, pattern_description: str) -> str:
        return f"""
Je bent een HR Manager voor een AI-agent team.
Zoek online naar maximaal 3 relevante, gezaghebbende trainingsbronnen
voor een agent met rol '{agent_role}' met deze ontwikkelgap:
"{pattern_description}".

Geef ALLEEN JSON terug (zonder markdown):
[
  {{
    "url": "https://...",
    "title": "Paginatitel",
    "rationale": "Waarom dit direct helpt voor deze gap (max 100 woorden)"
  }}
]
""".strip()

    async def _search_with_claude(self, prompt: str) -> list[dict]:
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            logger.warning("[HRResourceDiscovery] ANTHROPIC_API_KEY not set")
            return []

        payload = {
            "model": DEFAULT_MODEL,
            "max_tokens": 1200,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": "web-search-2025-03-05",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            logger.warning("[HRResourceDiscovery] web_search request failed: %s", exc)
            return []

        text_blocks = [
            b.get("text", "")
            for b in data.get("content", [])
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        raw = "\n".join(text_blocks).strip()
        if not raw:
            return []

        # Robust parsing: first try direct JSON, then first JSON array block.
        try:
            parsed = json.loads(raw)
        except Exception:
            match = re.search(r"\[\s*\{.*\}\s*\]", raw, flags=re.S)
            if not match:
                return []
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                return []

        if not isinstance(parsed, list):
            return []

        cleaned: list[dict] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                continue
            cleaned.append(
                {
                    "url": url,
                    "title": str(item.get("title") or "").strip(),
                    "rationale": str(item.get("rationale") or "").strip(),
                }
            )
        return cleaned
