"""
Analysis Agent - synthese van ruwe kanaaldata naar kwalitatieve vergelijking.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _fmt_num(value: Any) -> str:
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except Exception:
        return str(value)


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
    paid_available = "google_ads" in available_integrations and bool(raw_data.get("google_ads"))
    if paid_available:
        paid_line = "Paid (Google Ads): data beschikbaar en meegenomen in vergelijking."
    elif "google_ads" in missing_integrations:
        paid_line = "Paid (Google Ads): Niet beschikbaar - koppeling niet actief voor deze klant."
    else:
        paid_line = "Paid (Google Ads): Niet beschikbaar - geen bruikbare dataset ontvangen."

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
