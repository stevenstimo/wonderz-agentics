"""
Deterministische skill matching voor de CEO-orchestrator.
Geen LLM: keyword overlap + prioriteit (tie-break: priority DESC, skill_id).
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import asyncpg

def _matched_skill_payload(row: asyncpg.Record | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    return {
        "skill_id": d.get("skill_id"),
        "skill_name": d.get("skill_name"),
        "agent_type": d.get("agent_type"),
        "tool_name": d.get("tool_name"),
        "description": d.get("description"),
        "priority": d.get("priority"),
    }


async def match_skill(
    conn: asyncpg.Connection, job_description: str
) -> Optional[dict[str, Any]]:
    """
    Beste skill op basis van aantal keyword-hits (case-insensitive).
    Minstens één keyword moet matchen. Bij gelijke score: hoogste priority, dan skill_id.
    """
    if not job_description or not str(job_description).strip():
        return None

    rows = await conn.fetch(
        """
        SELECT skill_id, skill_name, description, trigger_keywords,
               agent_type, tool_name, priority
        FROM skill_registry
        WHERE is_active = true
        ORDER BY priority DESC, skill_id
        """
    )
    if not rows:
        return None

    description_lower = job_description.lower()
    description_clean = re.sub(r"[^\w\s]", " ", description_lower)

    best: Optional[dict[str, Any]] = None
    best_score = 0
    best_priority = -10_000
    best_id = ""

    for skill in rows:
        keywords = skill["trigger_keywords"] or []
        score = sum(1 for kw in keywords if kw and str(kw).lower() in description_clean)
        if score == 0:
            continue
        pri = int(skill["priority"] or 0)
        sid = str(skill["skill_id"] or "")
        if score > best_score or (
            score == best_score
            and (pri > best_priority or (pri == best_priority and sid < best_id))
        ):
            best_score = score
            best = _matched_skill_payload(skill)
            best_priority = pri
            best_id = sid

    return best


async def persist_matched_skill(
    conn: asyncpg.Connection, job_id: str, matched: dict[str, Any]
) -> None:
    """Schrijf matched_skill naar payload én context (jsonb_set)."""
    blob = json.dumps(matched)
    await conn.execute(
        """
        UPDATE jobs
        SET
            payload = jsonb_set(COALESCE(payload, '{}'::jsonb), $2::text[], $3::jsonb, true),
            context = jsonb_set(COALESCE(context, '{}'::jsonb), $2::text[], $3::jsonb, true),
            updated_at = now()
        WHERE id = $1::uuid
        """,
        job_id,
        ["matched_skill"],
        blob,
    )


async def get_all_skills(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT skill_id, skill_name, description, agent_type, tool_name,
               priority, is_active, trigger_keywords
        FROM skill_registry
        ORDER BY priority DESC, skill_name
        """
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if d.get("trigger_keywords") is not None:
            d["trigger_keywords"] = list(d["trigger_keywords"])
        out.append(d)
    return out


UNKNOWN_PRESET_AND_SKILL_MESSAGE = (
    "Onbekend jobtype. Geen passende preset of skill gevonden. "
    "Omschrijf de opdracht specifieker."
)
