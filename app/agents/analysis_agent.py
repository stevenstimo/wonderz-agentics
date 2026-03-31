"""
Analysis Agent - synthese van ruwe kanaaldata naar kwalitatieve vergelijking.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _fmt_num(value: Any) -> str:
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except Exception:
        return str(value)


def _google_ads_usable(raw: Any) -> bool:
    if not raw:
        return False
    if isinstance(raw, dict) and raw.get("available") is False:
        return False
    return True


def _summarize_ads(raw_ads: Dict[str, Any]) -> str:
    totals = raw_ads.get("totals") or {}
    n = len(raw_ads.get("campaigns") or [])
    spend = float(totals.get("spend", 0) or 0)
    clicks = int(totals.get("clicks", 0) or 0)
    impr = int(totals.get("impressions", 0) or 0)
    conv = float(totals.get("conversions", 0) or 0)
    dr = raw_ads.get("date_range") or ""
    suffix = f" ({dr})" if dr else ""
    return (
        f"Paid (Google Ads): {n} campagnes, €{spend:,.2f} spend, {_fmt_num(clicks)} clicks, "
        f"{_fmt_num(impr)} impressions, {_fmt_num(conv)} conversies{suffix}."
    )


def _summarize_gsc(raw_gsc: Dict[str, Any]) -> str:
    rows = raw_gsc.get("resultaat") or []
    if not rows:
        return "Geen bruikbare organische data gevonden in de gekozen periode."
    clicks = sum(float(r.get("clicks", 0) or 0) for r in rows if isinstance(r, dict))
    impressions = sum(float(r.get("impressions", 0) or 0) for r in rows if isinstance(r, dict))
    ctr = (clicks / impressions * 100.0) if impressions > 0 else 0.0
    return (
        f"Organisch (GSC): {len(rows)} pagina's, {_fmt_num(clicks)} clicks, "
        f"{_fmt_num(impressions)} impressions, CTR {ctr:.1f}%."
    )


async def run_analysis(
    job_id: str,
    client_name: str,
    raw_data: Dict[str, Any],
    available_integrations: List[str],
    missing_integrations: List[str],
    original_question: str,
) -> Dict[str, Any]:
    """
    Produceer een kwalitatieve analyse met expliciete labels voor ontbrekende bronnen.
    """
    gsc_summary = _summarize_gsc(raw_data.get("gsc") or {})

    ads_raw = raw_data.get("google_ads")
    paid_available = "google_ads" in available_integrations and _google_ads_usable(ads_raw)

    reden_map = {
        "no_credentials": "koppeling niet actief of customer ID ontbreekt",
        "token_error": "OAuth token verlopen of ongeldig",
        "no_campaigns": "geen actieve campagnes gevonden",
        "api_error": "API fout bij ophalen",
    }

    if paid_available and isinstance(ads_raw, dict):
        paid_line = _summarize_ads(ads_raw)
    elif "google_ads" in available_integrations and isinstance(ads_raw, dict) and ads_raw.get("available") is False:
        reden = reden_map.get(str(ads_raw.get("reason", "")), "onbekende reden")
        paid_line = f"Paid (Google Ads): Niet beschikbaar — {reden}."
    elif "google_ads" in missing_integrations:
        paid_line = "Paid (Google Ads): Niet beschikbaar — koppeling niet actief voor deze klant."
    else:
        paid_line = "Paid (Google Ads): Niet beschikbaar — onbekende reden."

    comparison_line = (
        "Vergelijking kan alleen volledig worden gemaakt zodra zowel organisch als paid data aanwezig zijn."
        if not paid_available
        else "Organisch en paid zijn beide beschikbaar; beoordeel verkeer- en efficiencymix per kanaal."
    )

    analysis = (
        f"**Gevonden**\n"
        f"- Vraag: {original_question}\n"
        f"- Klant: {client_name}\n"
        f"- {gsc_summary}\n"
        f"- {paid_line}\n\n"
        f"**Vergelijking**\n"
        f"- {comparison_line}\n\n"
        f"**Conclusie**\n"
        f"- Op basis van de beschikbare data is een organisch oordeel mogelijk; paid impact blijft voorlopig onzeker.\n\n"
        f"**Aanbeveling**\n"
        f"- Activeer Google Ads-koppeling en herhaal dezelfde periode voor een zuivere organisch-vs-paid vergelijking."
    )

    return {
        "status": "completed",
        "analysis": analysis,
        "available_integrations": available_integrations,
        "missing_integrations": missing_integrations,
        "token_usage": {"input": 0, "output": 0},
        "job_id": job_id,
    }


UNIVERSAL_SYNTHESIS_PROMPT = """
Je bent Harvey Specter, Analysis Agent binnen Wonderz Agentics.
Je taak: de originele vraag van de gebruiker beantwoorden op basis van de beschikbare data.

REGELS:
1. Lees de originele vraag goed. Beantwoord precies wat gevraagd wordt.
2. Gebruik de beschikbare data als basis. Geen claims zonder datapunt.
3. Als de data niet volledig is: zeg wat je WEL kunt beantwoorden en wat ontbreekt.
4. Schrijf in het Nederlands, direct en bondig.
5. Gebruik tabellen waar dat verduidelijkt - altijd met een inleidende zin.
6. Eindig met een concrete observatie die direct voortkomt uit de data.
7. Nooit generieke fallback-tekst. Altijd specifiek voor deze vraag en data.

OUTPUTSTRUCTUUR (pas aan op de vraag):
- Begin met directe beantwoording (1-2 zinnen)
- Toon de relevante data gestructureerd (tabel, lijst, of proza - wat past)
- Sluit af met een observatie of aanbeveling

RICHTLIJNEN PER VRAAGTYPE:
- Vergelijking tussen kanalen: gebruik Gevonden/Vergelijking/Conclusie/Aanbeveling format
- Overzicht of rapport: gebruik een tabel met uitleg
- Specifiek getal of feit: geef dat direct, dan context
"""


async def run_universal_synthesis(
    job_id: str,
    original_question: str,
    client_name: str,
    raw_data: Dict[str, Any],
    available_integrations: List[str],
    missing_integrations: List[str],
) -> Dict[str, Any]:
    """
    Universele synthese voor elke data-job.
    Beantwoordt de originele vraag op basis van de beschikbare data.
    """
    try:
        import anthropic
    except Exception as e:
        logger.error("UniversalSynthesis anthropic import fout voor job %s: %s", job_id, e)
        return {"status": "error", "error": f"anthropic import error: {e}", "analysis": None}
    client = anthropic.AsyncAnthropic()

    data_context_parts: List[str] = []
    for integration, data in (raw_data or {}).items():
        if isinstance(data, dict) and data.get("available") is False:
            reden_map = {
                "no_credentials": "koppeling niet actief",
                "token_error": "OAuth token verlopen of ongeldig",
                "no_campaigns": "geen actieve campagnes gevonden",
                "api_error": "API fout bij ophalen",
            }
            reden = reden_map.get(str(data.get("reason", "")), "onbekende reden")
            data_context_parts.append(
                f"**{str(integration).upper()} data:** Niet beschikbaar - {reden}."
            )
        elif data:
            data_context_parts.append(
                f"**{str(integration).upper()} data:**\n{json.dumps(data, indent=2, ensure_ascii=False)}"
            )

    for missing in (missing_integrations or []):
        data_context_parts.append(
            f"**{str(missing).upper()} data:** Niet beschikbaar - koppeling niet actief."
        )

    data_context = "\n\n".join(data_context_parts) if data_context_parts else "Geen data beschikbaar."
    user_message = f"""
Originele vraag: "{original_question}"
Klant: {client_name}
Job ID: {job_id}

Beschikbare data:
{data_context}

Beantwoord de vraag op basis van de beschikbare data.
"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            system=UNIVERSAL_SYNTHESIS_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        text = ""
        if getattr(response, "content", None):
            text = getattr(response.content[0], "text", "") or ""
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return {
            "status": "completed",
            "analysis": text,
            "available_integrations": available_integrations,
            "missing_integrations": missing_integrations,
            "token_usage": {"input": input_tokens, "output": output_tokens},
        }
    except Exception as e:
        logger.error("UniversalSynthesis fout voor job %s: %s", job_id, e)
        return {"status": "error", "error": str(e), "analysis": None}
