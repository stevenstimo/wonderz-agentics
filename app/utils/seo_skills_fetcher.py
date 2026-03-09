"""
Fetch SEO-specific skills by skill_id for injection into SEO Agent.
Uses deterministic skill_ids from spec; falls back gracefully if skills missing.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Spec: skill:seo:strategy-realistic-v2, skill:copywriting:seo,
# competitive-keyword-gap-analysis, keyword-scoring-prioritization-model
SEO_SKILL_IDS = [
    "skill:seo:strategy-realistic-v2",
    "skill:copywriting:seo",
    "competitive-keyword-gap-analysis",
    "keyword-scoring-prioritization-model",
]

MAX_CONTENT_CHARS = 6000


async def fetch_seo_skills(pool) -> str:
    """
    Fetch skills by skill_id and return formatted context string for SEO Agent.
    Returns empty string on failure (never block the agent).
    """
    try:
        async with pool.acquire() as conn:
            # Fetch by skill_id; use ANY for array match
            placeholders = ", ".join(f"${i+1}" for i in range(len(SEO_SKILL_IDS)))
            rows = await conn.fetch(
                f"SELECT skill_id, name, domain, content FROM agent_skills WHERE skill_id IN ({placeholders})",
                *SEO_SKILL_IDS,
            )
    except Exception as e:
        logger.warning("SEO skills fetch failed: %s; continuing without skills", e)
        return ""

    if not rows:
        logger.info("No SEO skills found in library; agent will run without skills context")
        return ""

    lines = [
        "---",
        "## ACTIVE SKILLS — Apply these frameworks to keyword analysis",
        "",
    ]
    for r in rows:
        content = (r.get("content") or "")[:MAX_CONTENT_CHARS]
        if len(r.get("content") or "") > MAX_CONTENT_CHARS:
            content += "\n\n[... truncated ...]"
        lines.append(f"### {r.get('name', 'Skill')}")
        lines.append(f"**skill_id:** {r.get('skill_id', '')}")
        lines.append(f"**domain:** {r.get('domain', '')}")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)
