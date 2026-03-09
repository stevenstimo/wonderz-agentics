"""Skills context builder — fetches relevant skills and formats for agent injection."""

import json
import logging
from typing import Any, Dict, List, Optional

from app.utils.skills_triggers import get_fallback_skills

logger = logging.getLogger(__name__)

# Max chars per skill content to avoid token overflow (approx 1500 tokens)
MAX_CONTENT_CHARS_PER_SKILL = 6000


async def get_relevant_skills(
    pool,
    task_description: str,
    domain: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Fetch skills relevant to a task. Uses Judson (Claude) to pick from library.
    Falls back to hardcoded trigger rules on failure.
    Returns {"skills": [...], "skill_ids": [...]}.
    """
    from anthropic import Anthropic

    # Fetch skills from library for Judson to choose from
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT skill_id, name, domain, content FROM agent_skills ORDER BY domain, name LIMIT 100"
        )
    skills_list = [dict(r) for r in rows]
    if not skills_list:
        return {"skills": [], "skill_ids": []}

    # Build summary for Judson (no full content in prompt)
    summary = [{"skill_id": s["skill_id"], "name": s["name"], "domain": s["domain"]} for s in skills_list]

    api_key = __import__("os").environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; using fallback trigger rules")
        skill_ids = _fallback_skill_ids(task_description, domain, limit)
    else:
        try:
            client = Anthropic()
            user_message = f"""
A GTM Agent has received this task:

"{task_description}"

Identify which skills from the library are relevant for this task.
Return ONLY a JSON array of skill_ids in priority order (most critical first).
Maximum {limit} skills.
Format: ["skill_id_1", "skill_id_2", ...]
No explanation. JSON only.

Available skills: {json.dumps(summary)}
"""
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text if response.content else ""
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[7:]
            if text.endswith("```"):
                text = text[:-3].strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                skill_ids = json.loads(text[start:end])
            else:
                skill_ids = []
        except Exception as e:
            logger.warning("Judson skills lookup failed: %s; using fallback", e)
            skill_ids = _fallback_skill_ids(task_description, domain, limit)

    if not skill_ids:
        return {"skills": [], "skill_ids": []}

    # Fetch full skill objects, preserve order
    skills_dict = {s["skill_id"]: s for s in skills_list}
    ordered = []
    for sid in skill_ids:
        if sid in skills_dict:
            s = skills_dict[sid]
            content = s.get("content") or ""
            if len(content) > MAX_CONTENT_CHARS_PER_SKILL:
                content = content[:MAX_CONTENT_CHARS_PER_SKILL] + "\n\n[... truncated ...]"
            ordered.append({
                "skill_id": s["skill_id"],
                "name": s["name"],
                "domain": s["domain"],
                "content": content,
            })

    if domain:
        ordered = [s for s in ordered if s.get("domain") == domain]

    return {"skills": ordered, "skill_ids": [s["skill_id"] for s in ordered]}


def _fallback_skill_ids(task_description: str, domain: Optional[str], limit: int) -> List[str]:
    """Infer task type from description and return fallback skill_ids."""
    task_lower = (task_description or "").lower()
    if any(kw in task_lower for kw in ("gtm", "go-to-market", "marktintroductie", "market entry", "verzekering", "regul")):
        return get_fallback_skills("market_entry")[:limit]
    if any(kw in task_lower for kw in ("seo", "zoekmachine")):
        return get_fallback_skills("seo")[:limit]
    if any(kw in task_lower for kw in ("content", "contentkalender")):
        return get_fallback_skills("content")[:limit]
    return get_fallback_skills("gtm")[:limit]


async def build_skills_context(
    pool,
    task_description: str,
    domain: Optional[str] = None,
    limit: int = 5,
) -> tuple[str, List[str]]:
    """
    Fetches relevant skills and formats as injectable context.
    Returns (context_string, skill_ids_used).
    Returns ("", []) on failure (never block the agent).
    """
    try:
        result = await get_relevant_skills(
            pool=pool,
            task_description=task_description,
            domain=domain,
            limit=limit,
        )
        skills = result.get("skills", [])
        skill_ids = result.get("skill_ids", [])

        if not skills:
            return "", []

        lines = [
            "---",
            "## ACTIVE SKILLS — Apply these frameworks to this task",
            "",
        ]
        for s in skills:
            lines.append(f"### {s.get('name', 'Skill')}")
            lines.append(f"**skill_id:** {s.get('skill_id', '')}")
            lines.append(f"**domain:** {s.get('domain', '')}")
            lines.append("")
            lines.append(s.get("content", ""))
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines), skill_ids
    except Exception as e:
        logger.warning("Skills context build failed: %s", e)
        return "", []
