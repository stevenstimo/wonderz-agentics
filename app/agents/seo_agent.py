"""
SEO Agent — analyses keywords, determines intent, silo, content type, title suggestions.
Uses skills from library (skill:seo:strategy-realistic-v2, skill:copywriting:seo, etc.)
and processes keywords in batches of 50.
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from app.core.config import DEFAULT_MODEL
from app.database import get_db
from app.utils.seo_skills_fetcher import fetch_seo_skills

logger = logging.getLogger(__name__)

SEO_MODEL = DEFAULT_MODEL
BATCH_SIZE = 50


def calculate_priority(volume: int, kd: float, position: Optional[int]) -> str:
    """Priority from spec: volume * (1 - KD/100), bonus for position 1-20."""
    score = volume * (1 - kd / 100)
    if position and 0 < position <= 20:
        score *= 1.5
    if score > 5000:
        return "HIGH"
    elif score > 1000:
        return "MEDIUM"
    return "LOW"


def _call_anthropic_sync(system: str, user_prompt: str, model: str = SEO_MODEL) -> Dict[str, Any]:
    """Sync Anthropic call — runs in thread pool from async context."""
    client = Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = msg.content[0].text if msg.content else ""
    return {"text": text}


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    """Extract JSON array from response, handling markdown code blocks."""
    text = (text or "").strip()
    # Strip ```json ... ```
    if "```" in text:
        start = text.find("```")
        if start >= 0:
            rest = text[start:]
            if rest.startswith("```json"):
                rest = rest[7:]
            elif rest.startswith("```"):
                rest = rest[3:]
            end = rest.find("```")
            if end >= 0:
                rest = rest[:end]
            text = rest.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return []


async def process_keyword_batch(
    keywords: List[Dict[str, Any]],
    brand_name: str,
    domain: str,
    audience: str,
    language: str,
    skills_context: str,
) -> List[Dict[str, Any]]:
    """
    Process one batch of keywords via Claude. Returns list of enriched keyword dicts.
    """
    batch_data = [
        {
            "keyword": k["keyword"],
            "volume": k.get("volume", 0),
            "kd": k.get("kd", 0),
            "position": k.get("position"),
            "cpc": k.get("cpc"),
            "current_url": k.get("current_url"),
        }
        for k in keywords
    ]

    user_prompt = f"""Gegeven deze keywords met volume en KD:

{json.dumps(batch_data, ensure_ascii=False, indent=2)}

Brand context: {brand_name} | Domein: {domain} | Doelgroep: {audience} | Taal: {language}

Per keyword, bepaal:
1. intent: informational / commercial / transactional / navigational
2. silo: thematische cluster (max 6 silo's voor de hele set — gebruik consistente silo namen)
3. content_type: Blog / Landing Page / Pillar Page
4. title: SEO-geoptimaliseerde {language.upper()}-talige titelsuggestie (max 60 tekens)
5. primary_source: NHG / Overheid / Universiteit / Expert / Intern
6. audience_match: welke persona past bij dit keyword

Return ALLEEN een JSON array — geen andere tekst. Eén object per keyword, in dezelfde volgorde als de input.
Format: [{{"keyword":"...","intent":"...","silo":"...","content_type":"...","title":"...","primary_source":"...","audience_match":"..."}}, ...]"""

    system = """Je bent een SEO specialist. Analyseer keywords en geef gestructureerde JSON terug.
Volg strikt het gevraagde format. Geen uitleg, alleen de JSON array."""
    if skills_context:
        system = system + "\n\n" + skills_context

    result = await asyncio.to_thread(_call_anthropic_sync, system, user_prompt)
    text = result.get("text", "")
    parsed = _parse_json_array(text)

    # Merge AI output with original keyword data
    enriched = []
    for i, k in enumerate(keywords):
        base = dict(k)
        if i < len(parsed) and isinstance(parsed[i], dict):
            p = parsed[i]
            base["intent"] = p.get("intent") or "informational"
            base["silo"] = p.get("silo") or "Overig"
            base["content_type"] = p.get("content_type") or "Blog"
            base["title_suggestion"] = p.get("title") or p.get("title_suggestion") or ""
            base["primary_source"] = p.get("primary_source") or "Expert"
            base["audience_match"] = p.get("audience_match") or audience
        else:
            base["intent"] = "informational"
            base["silo"] = "Overig"
            base["content_type"] = "Blog"
            base["title_suggestion"] = ""
            base["primary_source"] = "Expert"
            base["audience_match"] = audience

        base["priority"] = calculate_priority(
            base.get("volume", 0),
            base.get("kd", 0),
            base.get("position"),
        )
        enriched.append(base)

    return enriched


async def run_seo_agent(
    job_id: str,
    keywords: List[Dict[str, Any]],
    brand_name: str,
    domain: str,
    audience: str,
    language: str,
    progress_callback: Optional[callable] = None,
) -> List[Dict[str, Any]]:
    """
    Run SEO Agent on all keywords in batches. Calls progress_callback(processed, total, current_silo)
    after each batch. Returns full list of enriched keywords.
    """
    pool = await get_db()
    skills_context = await fetch_seo_skills(pool)
    if skills_context:
        logger.info("SEO Agent: injected skills context")

    all_enriched: List[Dict[str, Any]] = []
    total = len(keywords)
    for offset in range(0, total, BATCH_SIZE):
        batch = keywords[offset : offset + BATCH_SIZE]
        enriched = await process_keyword_batch(
            batch, brand_name, domain, audience, language, skills_context
        )
        all_enriched.extend(enriched)
        current_silo = enriched[-1].get("silo", "") if enriched else ""
        if progress_callback:
            progress_callback(len(all_enriched), total, current_silo)
    return all_enriched
