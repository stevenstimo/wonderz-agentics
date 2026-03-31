"""
Deterministic silo, audience, SERP shortening, and priority scoring for SEO keyword plans.
Replaces LLM-assigned silo/Overig buckets and aligns with Semrush Page + keyword rules.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.utils.seo_parser import _parse_trend_monthly_from_cell

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

INTENT_LABELS_ALLOWED = frozenset({"informational", "commercial", "transactional", "navigational"})


def normalize_intent(val: Any) -> str:
    """
    Multi-intent: komma-gescheiden canonieke labels (Informational, Commercial, …).
    Accepteert string, JSON-list of gemengde CSV; geen onbekende tokens; dedupe op lowercase.
    """
    if val is None:
        return "informational"
    if isinstance(val, list):
        raw_parts = [str(x).strip() for x in val if x is not None and str(x).strip()]
        raw = ", ".join(raw_parts)
    else:
        raw = str(val).strip()
    if not raw:
        return "informational"
    segments = re.split(r"[,;/|]+", raw)
    out: List[str] = []
    seen_lower: set[str] = set()
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        token = seg.lower().split()[0]
        if token not in INTENT_LABELS_ALLOWED:
            continue
        label = token.capitalize()
        if token not in seen_lower:
            seen_lower.add(token)
            out.append(label)
    if not out:
        return "informational"
    return ", ".join(out)


def primary_intent_for_scoring(intent: str) -> str:
    """Eén label voor priority/click-heuristiek: sterkste transactie-intent wint."""
    s = (intent or "").lower()
    found: List[str] = []
    for part in re.split(r"[,;/|]+", s):
        t = part.strip().split()[0] if part.strip() else ""
        if t in INTENT_LABELS_ALLOWED and t not in found:
            found.append(t)
    if not found:
        return "informational"
    for pref in ("transactional", "commercial", "navigational", "informational"):
        if pref in found:
            return pref
    return found[0]


def _is_missing_page(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in ("", "nan", "-", "none", "n/a", "#n/a")


def standardize_silo_name(silo: str, keyword: str, page_cluster: Any) -> str:
    """
    Title-case descriptive silo label, max 4 words.
    When cluster equals keyword (raw URL slug / keyword string), derive a short label from the keyword.
    """
    s = (silo or "").strip()
    kw = (keyword or "").strip()
    cl = str(page_cluster or "").strip()
    if not s:
        return s
    if kw and cl and kw.lower() == cl.lower():
        parts = re.split(r"[\s\-_/]+", kw)
        parts = [p for p in parts if p][:4]
        s = " ".join(parts) if parts else s
    elif kw and s.lower() == kw.lower():
        parts = re.split(r"[\s\-_/]+", kw)
        parts = [p for p in parts if p][:4]
        s = " ".join(parts) if parts else s
    words = s.split()
    words = words[:4]
    out: List[str] = []
    for w in words:
        if w.isupper() or w.islower():
            out.append(w[:1].upper() + w[1:].lower() if len(w) > 1 else w.upper())
        else:
            out.append(w)
    return " ".join(out)


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


def audience_for_intent_silo(intent: str, silo: str) -> str:
    """Funnel-achtige doelgroep; ondersteunt meerdere intent-labels (komma's) via woordgrenzen."""
    s = (intent or "").lower()
    silo_l = (silo or "").strip().lower()
    broad = (
        silo_l == FALLBACK_SILO.lower()
        or "algemeen" in silo_l
        or (not silo_l)
    )

    def _has(word: str) -> bool:
        return bool(re.search(rf"\b{re.escape(word)}\b", s))

    if _has("navigational"):
        return "Bestaande klant / merkbekende"
    if _has("transactional"):
        return "Koopklaar bezoeker (BOFU)"
    if _has("commercial"):
        return "Koopgereed bezoeker (BOFU)"
    if _has("informational"):
        if broad:
            return "Oriënterende reiziger (TOFU)"
        return "Specifieke interesse (MOFU)"
    return "Specifieke interesse (MOFU)"


def classify_trend(monthly_volumes: List[float]) -> str:
    """Vergelijk eerste vs laatste drie maanden (doc SEO output kwaliteit)."""
    if not monthly_volumes or len(monthly_volumes) < 3:
        return "? Onbekend"
    non_zero = sum(1 for x in monthly_volumes if x and x > 0)
    if non_zero < 2:
        return "? Onbekend"
    recent = sum(monthly_volumes[-3:]) / 3
    older = sum(monthly_volumes[:3]) / 3
    if older == 0:
        return "? Onbekend"
    delta = (recent - older) / older
    if delta > 0.20:
        return "↑ Stijgend"
    if delta < -0.20:
        return "↓ Dalend"
    return "→ Stabiel"


def map_trend_from_raw(raw: Any) -> str:
    """Semrush Trend-kolom of emoji."""

    if raw is None:
        return "? Onbekend"
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "-", "#n/a"):
        return "? Onbekend"
    low = s.lower()
    if "↑" in s or "stijg" in low or "groei" in low or "growing" in low or "up" == low:
        return "↑ Stijgend"
    if "↓" in s or "dal" in low or "declin" in low or "falling" in low or "down" == low:
        return "↓ Dalend"
    if "→" in s or "stab" in low or "stable" in low or "unchanged" in low:
        return "→ Stabiel"
    try:
        n = float(s.replace(",", ".").replace("%", ""))
        if n > 5:
            return "↑ Stijgend"
        if n < -5:
            return "↓ Dalend"
        return "→ Stabiel"
    except (TypeError, ValueError):
        return "? Onbekend"


def derive_trend_for_keyword(k: Dict[str, Any]) -> str:
    vols = k.get("trend_monthly_volumes")
    if not vols or len(vols) < 3:
        raw = k.get("trend_raw")
        if raw:
            parsed = _parse_trend_monthly_from_cell(str(raw))
            if len(parsed) >= 3:
                vols = parsed
    if vols and len(vols) >= 3:
        t = classify_trend([float(x or 0) for x in vols])
        if t != "? Onbekend":
            return t
    return map_trend_from_raw(k.get("trend_raw"))


def calculate_click_potential_from_serp(serp_features: str, intent: str) -> float:
    """0–100 schaal op basis van SERP-features (korte labels) en intent."""
    base = 100.0
    s_low = (serp_features or "").lower()
    if "ads top" in s_low or "adwords top" in s_low:
        base -= 25
    if "adwords bottom" in s_low or "ads bottom" in s_low:
        base -= 10
    if "featured snippet" in s_low:
        base -= 15
    if "ai overview" in s_low:
        base -= 20
    if "shopping" in s_low:
        base -= 15
    if "knowledge panel" in s_low:
        base -= 10
    if "video" in s_low:
        base -= 5
    i = primary_intent_for_scoring(intent)
    if i == "navigational":
        base -= 20
    if i == "transactional":
        base += 10
    return max(0.0, min(100.0, round(base, 0)))


def apply_plan_calendar_suggestions(k: Dict[str, Any]) -> None:
    """Week- en statussuggesties na prioriteit + GSC (doc)."""
    pr = (k.get("priority") or "LOW").upper()
    gsc = k.get("gsc_label") or ""
    week = ""
    if pr == "HIGH" and gsc in ("🟡 Optimaliseer", "🟠 Aanpakken"):
        week = "Week 1–4"
    elif pr == "HIGH":
        week = "Week 5–8"
    elif pr == "MEDIUM":
        week = "Week 9–16"
    elif pr == "LOW":
        week = "Week 17+"
    k["plan_week"] = week
    k["plan_status"] = "📋 Gepland" if week else ""


def normalize_business_relevance(val: Any) -> str:
    if val is None:
        return "?"
    v = str(val).strip().upper()
    if v in ("?", "UNKNOWN", "ONBEKEND", ""):
        return "?"
    if v in ("HOOG", "HIGH", "H"):
        return "HOOG"
    if v in ("MEDIUM", "GEMIDDELD", "MED"):
        return "MEDIUM"
    if v in ("LAAG", "LOW", "L"):
        return "LAAG"
    return "?"


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
    """Set silo, serp_features_short, audience_match, trend, click_potential (in-place)."""
    k["intent"] = normalize_intent(k.get("intent"))
    silo = classify_silo(k.get("keyword") or "", k.get("cluster"))
    k["silo"] = standardize_silo_name(silo, k.get("keyword") or "", k.get("cluster"))
    raw_serp = k.get("serp_features_raw")
    k["serp_features"] = shorten_serp_features(raw_serp)
    intent = k["intent"]
    k["click_potential"] = calculate_click_potential_from_serp(k["serp_features"], intent)
    k["audience_match"] = audience_for_intent_silo(intent, k["silo"])
    k["trend"] = derive_trend_for_keyword(k)


def apply_priority_after_gsc(k: Dict[str, Any]) -> None:
    """Recompute priority using GSC-aware scoring."""
    k["priority"] = calculate_priority(
        k.get("volume", 0),
        k.get("kd", 0),
        k.get("click_potential"),
        k.get("gsc_position"),
        k.get("gsc_label") or "⬜ Ontbreekt",
    )
