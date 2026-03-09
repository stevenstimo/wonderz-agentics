"""
GTM Agent — Growth, Marketing & Go-To-Market specialist.
Combineert Growth Hacker + Content Creator + Trend Researcher + Feedback Synthesizer.
Skills injection: loads relevant skills from library before each task.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from app.config.gtm_platforms import get_platform_context
from app.database import get_db
from app.utils.skills_context import build_skills_context

logger = logging.getLogger(__name__)

# ASSUMPTION-BASED: Use project's standard model; claude-sonnet-4-6 from spec may not exist yet
GTM_MODEL = "claude-sonnet-4-5-20250929"

# ASSUMPTION-BASED: Anthropic client is sync; we run it via asyncio.to_thread to avoid blocking
# ASSUMPTION-BASED: JSON output may be wrapped in markdown code blocks; we strip ```json ... ``` before parse

GTM_SYSTEM_PROMPT = """
Je bent de GTM Agent van Wonderz — een gespecialiseerde growth en marketing expert.

Je combineert vier specialismen:
1. Growth Hacker — viral loops, funnel optimalisatie, K-factor > 1.0
2. Content Creator — multi-platform content, 5:1 content ROI
3. Trend Researcher — marktintelligentie, weak signals 3-6 maanden vooruit
4. Feedback Synthesizer — user feedback → RICE-geprioriteerde acties

## Kritische regels
- Elke claim heeft een metric (geen vage uitspraken)
- Elke kanaalstrategie heeft een CAC-schatting
- Elke trend prediction heeft een tijdlijn en bronnen
- Platform-specifieke tone — nooit generiek

## Output formaten
Je geeft altijd gestructureerde JSON output terug zodat de Wonderz pipeline
ermee kan werken. Zie de platform config voor KPI targets.

[PLATFORM_CONTEXT wordt hieronder geïnjecteerd bij elke aanroep]
"""


def _call_anthropic_sync(
    system: str,
    user_prompt: str,
    model: str = GTM_MODEL,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """Sync Anthropic API call — runs in thread pool from async context."""
    client = Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    response_text = message.content[0].text
    usage = {
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }
    return {"text": response_text, "usage": usage}


async def run_gtm_agent(
    job_id: str,
    task_type: str,  # 'channel_strategy' | 'content_calendar' | 'trend_research' | 'feedback_synthesis'
    platform: str,   # 'wonderz' | 'clawagency' | 'blogable'
    job_brief: str,
    context: Optional[Dict[str, Any]] = None,
    handoff_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Voer GTM Agent uit voor een specifieke taak.

    Returns:
        dict met 'output', 'evidence', 'next_steps', 'metrics_to_track', 'skills_applied', 'skill_ids_used'
    """
    platform_config = get_platform_context(platform)

    # Step 1: Fetch relevant skills from library
    skills_context = ""
    skill_ids_used: List[str] = []
    try:
        pool = await get_db()
        skills_context, skill_ids_used = await build_skills_context(
            pool=pool,
            task_description=job_brief,
            domain="strategy",
            limit=5,
        )
    except Exception as e:
        logger.warning("Skills context fetch failed: %s; continuing without skills", e)

    # Bouw system prompt met platform context + skills
    system = (
        GTM_SYSTEM_PROMPT
        + f"\n\n## Platform Context\n{json.dumps(platform_config, indent=2, ensure_ascii=False)}"
    )
    if skills_context:
        system = system + "\n\n" + skills_context
        logger.info("GTM Agent: injected %d skills: %s", len(skill_ids_used), skill_ids_used)

    # Bouw user prompt op basis van taaktype
    task_prompts = {
        "channel_strategy": f"""
Analyseer de volgende job brief en maak een kanaalstrategie voor platform '{platform}'.

Job brief: {job_brief}
Extra context: {json.dumps(context or {}, ensure_ascii=False)}

Lever JSON op met:
- channel_analysis (per kanaal: hypothesis, cac, ltv, budget, timeline, k_factor_impact)
- viral_mechanic (concrete beschrijving + K-factor berekening)
- priority_order (kanalen gesorteerd op RICE score)
- week_1_actions (wat vandaag/deze week te doen)
- success_metrics (exacte KPIs met drempelwaarden)
""",
        "content_calendar": f"""
Maak een 4-weeks content kalender voor platform '{platform}'.

Job brief: {job_brief}
Extra context: {json.dumps(context or {}, ensure_ascii=False)}

Lever JSON op met posts per week per kanaal:
- hook (eerste woorden/zin)
- body_summary
- cta
- best_time
- repurposing instructies
- verwacht engagement rate
""",
        "trend_research": f"""
Analyseer markttrends relevant voor platform '{platform}'.

Onderwerp: {job_brief}
Extra context: {json.dumps(context or {}, ensure_ascii=False)}

Lever JSON op met per trend:
- naam, signal_strength, time_to_mainstream
- relevantie per platform (wonderz/clawagency/blogable)
- concrete actie-items
- bronnen
""",
        "feedback_synthesis": f"""
Analyseer de volgende feedback en prioriteer acties voor platform '{platform}'.

Feedback/data: {job_brief}
Extra context: {json.dumps(context or {}, ensure_ascii=False)}

Lever JSON op met:
- pain_points (gesorteerd op frequentie + impact)
- rice_scores per potentiële actie
- churn_risk_indicators
- recommended_next_features
- quick_wins (< 1 week implementatie)
""",
    }

    user_prompt = task_prompts.get(
        task_type, f"Voer GTM taak uit: {job_brief}"
    )

    # Voeg handoff context toe als die er is
    if handoff_context:
        user_prompt += (
            f"\n\nContext van vorige agent:\n{json.dumps(handoff_context, ensure_ascii=False)}"
        )

    # Run blocking Anthropic call in thread pool
    result = await asyncio.to_thread(
        _call_anthropic_sync,
        system=system,
        user_prompt=user_prompt,
    )

    response_text = result["text"]
    usage = result["usage"]

    # Probeer JSON te parsen (extract from markdown code block if needed)
    output: Dict[str, Any]
    try:
        # Strip markdown code blocks if present
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        output = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("GTM Agent response was not valid JSON: %s", e)
        output = {"raw_output": response_text, "parse_error": True}

    tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

    return {
        "output": output,
        "evidence": [f"GTM Agent output voor {task_type} op platform {platform}"],
        "next_steps": output.get("week_1_actions", output.get("quick_wins", [])),
        "metrics_to_track": output.get("success_metrics", {}),
        "tokens_used": tokens_used,
        "skills_applied": bool(skill_ids_used),
        "skill_ids_used": skill_ids_used,
    }
