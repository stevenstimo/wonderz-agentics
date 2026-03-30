"""
Deterministic silo, audience, SERP shortening, and priority scoring for SEO keyword plans.
Replaces LLM-assigned silo/Overig buckets and aligns with Semrush Page + keyword rules.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Exact / substring overrides (keyword lower)
SILO_MAP: Dict[str, str] = {
    "verzekering huurauto buitenland": "Huurauto Verzekeringen",
    "rondreis camper": "Camper Reizen",
    "gevaarlijkste land ter wereld": "Reisadviezen & Veiligheid",
    "simpele camping gerechten": "Camping Lifestyle",
    "greenwheels eigen risico": "Deelauto Verzekeringen",
}

# (token substrings to match in keyword lower), silo name — first match wins; order matters
KEYWORD_SILO_RULES: List[Tuple[List[str], str]] = [
    (["reisverzekering", "annulering", "kortlopend", "doorlopend"], "Reisverzekeringen"),
    (["reisadvies", "reisadvie"], "Reisadviezen Landen"),
    (["paspoort", "visum", "eta "], "Reisdocumenten"),
    (["winterbanden"], "Verkeersregels Europa"),
    (["pechhulp"], "Pechhulp & Bijstand"),
    (["anwb", "allianz", "fbto", "unive", "oom ver", "nkc ver"], "Merk & Vergelijking"),
    (["camper"], "Camper Verzekeringen"),
    (["cdw", "collision damage", "eigen risico camper"], "Verzekering Uitleg"),
    (["knokkelkoorts", "repatri", "ziekte"], "Medische Info Reizen"),
]

DOELGROEP_MAP: Dict[str, str] = {
    "Huurauto Verzekeringen": "Autohuurders",
    "Camper Reizen": "Camperreizigers",
    "Camper Verzekeringen": "Camperreizigers",
    "Reisadviezen Landen": "Reizigers naar risicolanden",
    "Reisadviezen & Veiligheid": "Reizigers naar risicolanden",
    "Reisdocumenten": "Internationale reizigers",
    "Medische Info Reizen": "Reizigers buitenland",
    "Merk & Vergelijking": "Vergelijkers & switchers",
    "Reisverzekeringen": "Vakantiegangers",
    "_default": "Brede reizigersmarkt",
}

FALLBACK_SILO = "Algemene reiscontent"

PRIORITY_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _is_missing_page(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in ("", "nan", "-", "none", "n/a", "#n/a")


def classify_silo(keyword: str, page_cluster: Any) -> str:
    """
    Primary: Semrush Page (cluster) when present.
    Else: SILO_MAP, then keyword_silo_rules, else fallback (never 'Overig').
    """
    kw = (keyword or "").strip()
    k_low = kw.lower()

    if not _is_missing_page(page_cluster):
        return str(page_cluster).strip()

    for phrase, silo in SILO_MAP.items():
        if phrase in k_low or k_low == phrase:
            return silo

    for tokens, silo in KEYWORD_SILO_RULES:
        for t in tokens:
            if t in k_low:
                return silo

    return FALLBACK_SILO


def audience_for_silo(silo: str) -> str:
    return DOELGROEP_MAP.get(silo) or DOELGROEP_MAP["_default"]


PRIORITY_FEATURES_SHORT: Dict[str, str] = {
    "featured snippet": "Featured Snippet",
    "people also ask": "PAA",
    "ai overview": "AI Overview",
    "video": "Video",
    "image pack": "Image Pack",
    "adwords top": "Ads Top",
    "site links": "Site Links",
    "knowledge panel": "Knowledge Panel",
    "local pack": "Local Pack",
}


def shorten_serp_features(raw: Any) -> str:
    """Map verbose Semrush SERP features to short labels; deduplicate."""
    if raw is None or (isinstance(raw, float) and str(raw) == "nan"):
        return ""
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "-", "none"):
        return ""
    # Split on common delimiters
    parts = re.split(r"[,;|/\n]+", s)
    seen: set[str] = set()
    out: List[str] = []
    for p in parts:
        p_clean = p.strip()
        if not p_clean:
            continue
        low = p_clean.lower()
        short = None
        for needle, label in PRIORITY_FEATURES_SHORT.items():
            if needle in low:
                short = label
                break
        if short is None:
            # Title-case short unknown fragments (max ~40 chars)
            short = p_clean[:40] if len(p_clean) <= 40 else p_clean[:37] + "..."
        if short not in seen:
            seen.add(short)
            out.append(short)
    return ", ".join(out)


def _parse_click_potential(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        s = str(val).replace(",", ".").replace("%", "").strip()
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def calculate_priority(
    volume: Any,
    kd: Any,
    click_potential: Any,
    gsc_position: Optional[float],
    gsc_status: str,
) -> str:
    """Scoring-based priority. Veto: KD > 45 without GSC ranking → LOW."""
    vol = int(volume) if volume is not None else 0
    try:
        kd_f = float(kd) if kd is not None else 50.0
    except (TypeError, ValueError):
        kd_f = 50.0
    cp = _parse_click_potential(click_potential)

    if kd_f > 45 and gsc_position is None:
        return "LOW"

    score = 0

    if vol >= 5000:
        score += 3
    elif vol >= 1000:
        score += 2
    elif vol >= 300:
        score += 1

    if kd_f <= 15:
        score += 3
    elif kd_f <= 25:
        score += 2
    elif kd_f <= 35:
        score += 1

    if cp >= 75:
        score += 2
    elif cp >= 50:
        score += 1

    if gsc_status in ("🟠 Aanpakken", "🔴 Zwak"):
        score += 2
    elif gsc_status == "🟡 Optimaliseer":
        score += 3

    if score >= 7:
        return "HIGH"
    if score >= 4:
        return "MEDIUM"
    return "LOW"


def cap_content_gap_priority(priority: str, kd: Any, gsc_position: Optional[float]) -> str:
    """KD > 45 and not ranking in top 100 → at most MEDIUM."""
    try:
        kd_f = float(kd) if kd is not None else 0.0
    except (TypeError, ValueError):
        kd_f = 0.0
    already_ranking = gsc_position is not None and float(gsc_position) <= 100
    if kd_f > 45 and not already_ranking:
        if PRIORITY_ORDER.get(priority, 0) >= PRIORITY_ORDER["HIGH"]:
            return "MEDIUM"
    return priority


def quick_win_score(
    volume: Any,
    kd: Any,
    clicks_gsc: Any,
    position_gsc: Optional[float],
) -> float:
    vol = float(volume) if volume is not None else 0.0
    try:
        kd_f = float(kd) if kd is not None else 0.0
    except (TypeError, ValueError):
        kd_f = 0.0
    try:
        clicks = float(clicks_gsc) if clicks_gsc is not None else 0.0
    except (TypeError, ValueError):
        clicks = 0.0
    pos = float(position_gsc) if position_gsc is not None else 50.0
    score = (vol / 100.0) + (clicks * 2.0) + ((21.0 - min(pos, 20.0)) * 3.0) - kd_f
    return round(score, 1)


def enrich_keyword_derived_fields(k: Dict[str, Any]) -> None:
    """Set silo, serp_features_short, audience_match from CSV + maps (in-place)."""
    silo = classify_silo(k.get("keyword") or "", k.get("cluster"))
    k["silo"] = silo
    k["audience_match"] = audience_for_silo(silo)
    raw_serp = k.get("serp_features_raw")
    k["serp_features"] = shorten_serp_features(raw_serp)


def apply_priority_after_gsc(k: Dict[str, Any]) -> None:
    """Recompute priority using GSC-aware scoring."""
    k["priority"] = calculate_priority(
        k.get("volume", 0),
        k.get("kd", 0),
        k.get("click_potential"),
        k.get("gsc_position"),
        k.get("gsc_label") or "⬜ Ontbreekt",
    )
