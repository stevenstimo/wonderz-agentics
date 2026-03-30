"""
SEO Agent — analyses keywords, determines intent, silo, content type, title suggestions.
Uses skills from library (skill:seo:strategy-realistic-v2, skill:copywriting:seo, etc.)
and processes keywords in batches of 50.
"""
import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from anthropic import Anthropic

from app.core.config import DEFAULT_MODEL
from app.database import get_db
from app.utils.seo_classification import apply_priority_after_gsc, enrich_keyword_derived_fields
from app.utils.seo_skills_fetcher import fetch_seo_skills

logger = logging.getLogger(__name__)

SEO_MODEL = DEFAULT_MODEL
BATCH_SIZE = 50


def calculate_kd_client(kd: float, gsc_position: Optional[float]) -> Optional[float]:
    """
    KD-Client = KD adjusted by current GSC position (top 100 as threshold).
    Outside top 100 or no GSC data → return None.
    """
    if gsc_position is None or gsc_position > 100:
        return None
    if gsc_position <= 3:
        factor = 0.40
    elif gsc_position <= 10:
        factor = 0.60
    elif gsc_position <= 30:
        factor = 0.75
    elif gsc_position <= 100:
        factor = 0.90
    else:
        return None
    return round(kd * factor, 1)


def get_gsc_label(gsc_position: Optional[float]) -> str:
    """Label per keyword based on GSC position for Status (GSC) column."""
    if gsc_position is None or gsc_position > 100:
        return "⬜ Ontbreekt"
    if gsc_position <= 3:
        return "✅ Sterk"
    if gsc_position <= 10:
        return "🟡 Optimaliseer"
    if gsc_position <= 30:
        return "🟠 Aanpakken"
    return "🔴 Zwak"


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

Brand context: {brand_name} | Domein: {domain} | Taal: {language}

Per keyword, bepaal:
1. intent: informational / commercial / transactional / navigational
2. content_type: Blog / Landing Page / Pillar Page
3. title: specifieke, klikwaardige SEO-titel (max 60 tekens). Verwerk het zoekwoord exact of als variant. Kies één structuur naar intentie: informatief "Wat is [keyword]? Complete uitleg" / instructief "Hoe [keyword]: stap-voor-stap" / lijst "[Getal] beste [keyword] voor [doelgroep]" / vergelijkend "[A] vs [B]: welke [keyword]?". Geen clickbait, geen caps lock, geen uitroeptekens.
4. primary_source: NHG / Overheid / Universiteit / Expert / Intern

(Silo en doelgroep worden door het systeem toegepast op basis van Semrush-cluster en regels — niet invullen.)

Return ALLEEN een JSON array — geen andere tekst. Eén object per keyword, in dezelfde volgorde als de input.
Format: [{{"keyword":"...","intent":"...","content_type":"...","title":"...","primary_source":"..."}}, ...]"""

    system = """Je bent een SEO specialist. Analyseer keywords en geef gestructureerde JSON terug.
Volg strikt het gevraagde format. Geen uitleg, alleen de JSON array."""
    if skills_context:
        system = system + "\n\n" + skills_context

    result = await asyncio.to_thread(_call_anthropic_sync, system, user_prompt)
    text = result.get("text", "")
    parsed = _parse_json_array(text)

    # Merge AI output with original keyword data; silo/doelgroep/SERP from deterministic rules
    enriched = []
    for i, k in enumerate(keywords):
        base = dict(k)
        if i < len(parsed) and isinstance(parsed[i], dict):
            p = parsed[i]
            base["intent"] = p.get("intent") or "informational"
            base["content_type"] = p.get("content_type") or "Blog"
            base["title_suggestion"] = p.get("title") or p.get("title_suggestion") or ""
            base["primary_source"] = p.get("primary_source") or "Expert"
        else:
            base["intent"] = "informational"
            base["content_type"] = "Blog"
            base["title_suggestion"] = ""
            base["primary_source"] = "Expert"

        enrich_keyword_derived_fields(base)
        enriched.append(base)

    return enriched


def _apply_gsc_to_keyword(k: Dict[str, Any], gsc_lookup: Dict[str, Dict[str, Any]]) -> None:
    """Mutate keyword dict: add gsc_position, gsc_clicks, gsc_impressions, gsc_ctr, kd_client, gsc_label."""
    kw = (k.get("keyword") or "").strip()
    key_lower = kw.lower() if kw else ""
    gsc = gsc_lookup.get(key_lower) if gsc_lookup else None

    if not gsc:
        k["gsc_position"] = None
        k["gsc_clicks"] = None
        k["gsc_impressions"] = None
        k["gsc_ctr"] = None
        k["kd_client"] = None
        k["gsc_label"] = "⬜ Ontbreekt"
        apply_priority_after_gsc(k)
        return

    gsc_pos = gsc.get("position")
    k["gsc_position"] = gsc_pos
    k["gsc_clicks"] = gsc.get("clicks")
    k["gsc_impressions"] = gsc.get("impressions")
    k["gsc_ctr"] = gsc.get("ctr")
    kd = k.get("kd") or 0
    k["kd_client"] = calculate_kd_client(kd, gsc_pos)
    k["gsc_label"] = get_gsc_label(gsc_pos)
    apply_priority_after_gsc(k)


async def run_seo_agent(
    job_id: str,
    keywords: List[Dict[str, Any]],
    brand_name: str,
    domain: str,
    audience: str,
    language: str,
    gsc_data: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[..., Awaitable[None]]] = None,
) -> List[Dict[str, Any]]:
    """
    Run SEO Agent on all keywords in batches. Calls progress_callback(processed, total, current_silo)
    after each batch. Returns full list of enriched keywords with GSC fields when gsc_data is set.
    """
    pool = await get_db()
    skills_context = await fetch_seo_skills(pool)
    if skills_context:
        logger.info("SEO Agent: injected skills context")

    # Case-insensitive lookup for gsc_data (keyword -> { position, clicks, impressions, ctr })
    gsc_lookup: Dict[str, Dict[str, Any]] = {}
    if gsc_data:
        for kw, v in gsc_data.items():
            if isinstance(v, dict):
                gsc_lookup[(kw or "").lower().strip()] = v

    all_enriched: List[Dict[str, Any]] = []
    total = len(keywords)
    for offset in range(0, total, BATCH_SIZE):
        batch = keywords[offset : offset + BATCH_SIZE]
        enriched = await process_keyword_batch(
            batch, brand_name, domain, audience, language, skills_context
        )
        for k in enriched:
            _apply_gsc_to_keyword(k, gsc_lookup)
        all_enriched.extend(enriched)
        current_silo = enriched[-1].get("silo", "") if enriched else ""
        if progress_callback:
            await progress_callback(len(all_enriched), total, current_silo)
    return all_enriched
