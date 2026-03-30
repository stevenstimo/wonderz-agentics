"""
SEO Plan Excel generator — Keyword Plan, Silo, Quick Wins, Strategie, Content Gaps,
GSC Performance, Markt Expansie (openpyxl).
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.utils.seo_classification import (
    cap_content_gap_priority,
    quick_win_score,
)

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill(start_color="2D2D2D", end_color="2D2D2D", fill_type="solid")
HEADER_FONT = Font(name="Arial", size=11, bold=True, color="FFFFFF")
HIGH_FILL = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
MEDIUM_FILL = PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid")
DATA_FONT = Font(name="Arial", size=10)

GSC_LABEL_FILLS = {
    "✅ Sterk": PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid"),
    "🟡 Optimaliseer": PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid"),
    "🟠 Aanpakken": PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid"),
    "🔴 Zwak": PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid"),
    "⬜ Ontbreekt": PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid"),
}

# Kolomvolgorde v2 — Markt … URL
KEYWORD_PLAN_COLUMNS = [
    "Markt",
    "Taal",
    "Keyword",
    "Cluster",
    "Silo",
    "Doelgroep",
    "Volume",
    "KD",
    "CPC",
    "Click Potential",
    "Intent",
    "SERP Features",
    "Status (GSC)",
    "Positie (GSC)",
    "Clicks (GSC)",
    "Impressies (GSC)",
    "CTR (GSC)",
    "Content Type",
    "Prioriteit",
    "Status",
    "Week",
    "URL",
]

CONTENT_GAPS_COLUMNS = [
    "Markt",
    "Keyword",
    "Volume",
    "KD",
    "Intent",
    "Silo",
    "Content Type",
    "Prioriteit",
]


def _taal_for_market(market: Any) -> str:
    m = str(market or "NL").strip().upper()
    if m == "UK":
        return "en"
    if m == "DE":
        return "de"
    return "nl"


def _ensure_output_dir() -> str:
    out_dir = "/tmp/seo_plans"
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def _row_fill_for_priority(priority: str) -> Optional[PatternFill]:
    if priority == "HIGH":
        return HIGH_FILL
    if priority == "MEDIUM":
        return MEDIUM_FILL
    return None


def _apply_header_style(ws, row_num: int = 1):
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT


def _auto_column_width(ws):
    for col in range(1, ws.max_column + 1):
        max_len = 15
        for row in range(1, min(ws.max_row + 1, 100)):
            val = ws.cell(row=row, column=col).value
            if val is not None:
                max_len = max(max_len, min(len(str(val)), 50))
        ws.column_dimensions[get_column_letter(col)].width = max_len


def _build_silo_overview(keywords: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    silos: Dict[str, Dict[str, Any]] = {}
    for k in keywords:
        silo = k.get("silo") or ""
        if not silo:
            continue
        if silo not in silos:
            silos[silo] = {"name": silo, "count": 0, "volume": 0, "kd_sum": 0, "content_types": set()}
        silos[silo]["count"] += 1
        silos[silo]["volume"] += k.get("volume") or 0
        silos[silo]["kd_sum"] += k.get("kd") or 0
        if k.get("content_type"):
            silos[silo]["content_types"].add(k["content_type"])

    result = []
    for s in silos.values():
        count = s["count"]
        avg_kd = s["kd_sum"] / count if count else 0
        ct = ", ".join(sorted(s["content_types"])) if s["content_types"] else "Blog"
        approach = f"Focus op {ct} content. Gemiddelde KD: {avg_kd:.0f}."
        result.append({
            "Silo naam": s["name"],
            "Aantal keywords": count,
            "Totaal volume": s["volume"],
            "Gemiddelde KD": round(avg_kd, 1),
            "Aanbevolen aanpak": approach,
        })
    return sorted(result, key=lambda x: -x["Totaal volume"])


def _ctr_display(ctr: Any) -> Any:
    if ctr is None:
        return None
    try:
        n = float(ctr)
        if n == 0:
            return "0.0%"
        return f"{n * 100:.1f}%"
    except (TypeError, ValueError):
        return None


def _keyword_plan_row_data(k: Dict[str, Any]) -> List[Any]:
    gsc_pos = k.get("gsc_position")
    gsc_clicks = k.get("gsc_clicks")
    gsc_imp = k.get("gsc_impressions")
    gsc_ctr = k.get("gsc_ctr")
    pos_display = gsc_pos if (gsc_pos is not None and gsc_pos != 0) else None
    mkt = k.get("market") or "NL"
    cp = k.get("click_potential")
    return [
        mkt,
        _taal_for_market(mkt),
        k.get("keyword") or "",
        k.get("cluster") or "",
        k.get("silo") or "",
        k.get("audience_match") or "",
        k.get("volume") if k.get("volume") is not None else None,
        k.get("kd") if k.get("kd") is not None else None,
        k.get("cpc") if k.get("cpc") is not None else None,
        round(float(cp), 1) if cp is not None else None,
        k.get("intent") or "",
        k.get("serp_features") or "",
        k.get("gsc_label") or None,
        pos_display,
        gsc_clicks,
        gsc_imp,
        _ctr_display(gsc_ctr) if gsc_ctr is not None else None,
        k.get("content_type") or "",
        k.get("priority") or "",
        "",
        "",
        k.get("current_url") or "",
    ]


def _filter_quick_wins(keywords: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Status Aanpakken/Optimaliseer, volume≥100, KD≤40; sort by quick_win_score DESC."""
    result = []
    for k in keywords:
        label = k.get("gsc_label") or ""
        if label not in ("🟠 Aanpakken", "🟡 Optimaliseer"):
            continue
        if (k.get("volume") or 0) < 100:
            continue
        if (k.get("kd") or 100) > 40:
            continue
        pos = k.get("gsc_position")
        if pos is None:
            continue
        k2 = dict(k)
        k2["quick_win_score"] = quick_win_score(
            k.get("volume", 0),
            k.get("kd", 0),
            k.get("gsc_clicks"),
            float(pos) if pos is not None else None,
        )
        result.append(k2)
    return sorted(result, key=lambda x: x.get("quick_win_score") or 0, reverse=True)


def _generate_strategy_metrics(
    keywords: List[Dict[str, Any]],
    silos: List[Dict[str, Any]],
    gsc_connected: bool,
) -> str:
    high = sum(1 for k in keywords if k.get("priority") == "HIGH")
    med = sum(1 for k in keywords if k.get("priority") == "MEDIUM")
    low = sum(1 for k in keywords if k.get("priority") == "LOW")
    total_vol = sum(k.get("volume") or 0 for k in keywords)
    nl = sum(1 for k in keywords if (k.get("market") or "NL").upper() == "NL")
    uk = sum(1 for k in keywords if (k.get("market") or "").upper() == "UK")
    de = sum(1 for k in keywords if (k.get("market") or "").upper() == "DE")
    lines = [
        "# Strategie — metrics",
        "",
        f"- Totaal keywords: {len(keywords)} | Totaal zoekvolume (som): {total_vol}",
        f"- Prioriteit: HIGH {high} | MEDIUM {med} | LOW {low}",
        f"- Markten in plan: NL {nl} | UK {uk} | DE {de}",
        f"- GSC-data gekoppeld: {'ja' if gsc_connected else 'nee (upload zonder client/GSC of geen token)'}",
        "",
        "## Focus silo's (top 5 op volume)",
    ]
    for s in silos[:5]:
        lines.append(
            f"- {s.get('Silo naam', '')}: {s.get('Aantal keywords', 0)} keywords, "
            f"volume {s.get('Totaal volume', 0)}, gem. KD {s.get('Gemiddelde KD', 0)}"
        )
    lines.extend([
        "",
        "## Aanbevolen volgorde",
        "1. Quick wins (🟡/🟠 in GSC, volume ≥100, KD ≤40)",
        "2. HIGH-prioriteit met haalbare KD",
        "3. MEDIUM clusters en uitbreiding UK/DE (zie tab Markt Expansie)",
    ])
    return "\n".join(lines)


def _write_gsc_performance_sheet(wb: openpyxl.Workbook, perf: Optional[Dict[str, Any]], site_url: Optional[str]) -> None:
    ws = wb.create_sheet("📊 GSC Performance")
    row = 1
    ws.cell(row=row, column=1, value="Google Search Console — overzicht (laatste periode)")
    row += 1
    if site_url:
        ws.cell(row=row, column=1, value=f"Property: {site_url}")
        row += 1
    if not perf:
        ws.cell(row=row, column=1, value="Geen GSC-data beschikbaar voor dit plan.")
        _auto_column_width(ws)
        return

    ws.cell(row=row, column=1, value=f"Periode: {perf.get('date_start')} — {perf.get('date_end')}")
    row += 2

    def _table(title: str, headers: List[str], rows: List[Dict[str, Any]], keys: List[str]):
        nonlocal row
        ws.cell(row=row, column=1, value=title)
        row += 1
        for c, h in enumerate(headers, 1):
            ws.cell(row=row, column=c, value=h)
        _apply_header_style(ws, row_num=row)
        row += 1
        for rdata in rows:
            for c, key in enumerate(keys, 1):
                ws.cell(row=row, column=c, value=rdata.get(key))
            row += 1
        row += 1

    tq = perf.get("top_queries") or []
    _table(
        "Top queries",
        ["Query", "Clicks", "Impressies", "CTR", "Positie"],
        tq,
        ["query", "clicks", "impressions", "ctr", "position"],
    )
    tp = perf.get("top_pages") or []
    _table(
        "Top pagina's",
        ["URL", "Clicks", "Impressies", "CTR", "Positie"],
        tp,
        ["page", "clicks", "impressions", "ctr", "position"],
    )
    tc = perf.get("countries") or []
    _table(
        "Landen",
        ["Land", "Clicks", "Impressies", "CTR", "Positie"],
        tc,
        ["country", "clicks", "impressions", "ctr", "position"],
    )
    ts = perf.get("timeseries") or []
    ws.cell(row=row, column=1, value="Trend (per dag)")
    row += 1
    for c, h in enumerate(["Datum", "Clicks", "Impressies"], 1):
        ws.cell(row=row, column=c, value=h)
    _apply_header_style(ws, row_num=row)
    row += 1
    for t in ts[:90]:
        ws.cell(row=row, column=1, value=t.get("date"))
        ws.cell(row=row, column=2, value=t.get("clicks"))
        ws.cell(row=row, column=3, value=t.get("impressions"))
        row += 1
    _auto_column_width(ws)


def _write_markt_expansie_sheet(wb: openpyxl.Workbook, keywords: List[Dict[str, Any]]) -> None:
    ws = wb.create_sheet("🌍 Markt Expansie UK+DE")
    instructions = [
        "Markt Expansie — UK en DE",
        "",
        "1. Exporteer in Semrush Keyword Magic Tool aparte clusters voor United Kingdom en Germany.",
        "2. Zelfde kolomstructuur als de NL-export (o.a. Keyword, Volume, KD, Page/Cluster, SERP Features).",
        "3. Upload het NL-bestand verplicht; voeg optioneel UK- en DE-export toe in dezelfde run (web UI).",
        "4. Alle rijen krijgen een Markt-kolom (NL / UK / DE) voor filter in Excel.",
        "",
        "Keywords in dit plan per markt:",
    ]
    row = 1
    for line in instructions:
        ws.cell(row=row, column=1, value=line)
        row += 1
    counts: Dict[str, int] = {}
    for k in keywords:
        m = (k.get("market") or "NL").upper()
        counts[m] = counts.get(m, 0) + 1
    for m in ("NL", "UK", "DE"):
        ws.cell(row=row, column=1, value=f"{m}: {counts.get(m, 0)} keywords")
        row += 1
    _auto_column_width(ws)


def generate_seo_excel(
    keywords: List[Dict[str, Any]],
    brand_name: str,
    strategy_notes: Optional[str] = None,
    gsc_site_url: Optional[str] = None,
    gsc_performance: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Multi-sheet Excel: Keyword Plan, Silo, Quick Wins, Strategie, Content Gaps,
    GSC Performance, Markt Expansie.
    """
    out_dir = _ensure_output_dir()
    safe_brand = "".join(c if c.isalnum() or c in " -_" else "_" for c in brand_name)[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"SEO_Plan_{safe_brand}_{timestamp}.xlsx"
    filepath = os.path.join(out_dir, filename)

    wb = openpyxl.Workbook()
    gsc_connected = any(
        k.get("gsc_position") is not None or (k.get("gsc_clicks") is not None and k.get("gsc_clicks") != 0)
        for k in keywords
    )

    # Sheet 1: Keyword Plan
    ws1 = wb.active
    ws1.title = "Keyword Plan"
    note = (
        f"GSC keyword-match: laatste 90 dagen — {gsc_site_url} | Paginated query export"
        if gsc_site_url
        else "GSC kolommen: geen koppeling of geen data — Status ⬜ Ontbreekt"
    )
    ws1.cell(row=1, column=1, value=note)
    for col, header in enumerate(KEYWORD_PLAN_COLUMNS, 1):
        ws1.cell(row=2, column=col, value=header)
    _apply_header_style(ws1, row_num=2)

    for row_idx, k in enumerate(keywords, 3):
        row_data = _keyword_plan_row_data(k)
        gsc_label = k.get("gsc_label")
        for col_idx, val in enumerate(row_data, 1):
            cell = ws1.cell(row=row_idx, column=col_idx, value=val)
            cell.font = DATA_FONT
            fill = GSC_LABEL_FILLS.get(gsc_label) if gsc_label else None
            if not fill:
                fill = _row_fill_for_priority(k.get("priority") or "")
            if fill:
                cell.fill = fill

    ws1.freeze_panes = "A3"
    ws1.auto_filter.ref = f"A2:{get_column_letter(ws1.max_column)}{ws1.max_row}"
    _auto_column_width(ws1)

    # Sheet 2: Silo Overzicht
    silos = _build_silo_overview(keywords)
    ws2 = wb.create_sheet("Silo Overzicht")
    silo_headers = ["Silo naam", "Aantal keywords", "Totaal volume", "Gemiddelde KD", "Aanbevolen aanpak"]
    for col, h in enumerate(silo_headers, 1):
        ws2.cell(row=1, column=col, value=h)
    _apply_header_style(ws2)
    for row_idx, s in enumerate(silos, 2):
        for col_idx, key in enumerate(silo_headers, 1):
            ws2.cell(row=row_idx, column=col_idx, value=s.get(key, ""))
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:{get_column_letter(len(silo_headers))}{ws2.max_row}"
    _auto_column_width(ws2)

    # Sheet 3: Quick Wins
    quick = _filter_quick_wins(keywords)
    quick_headers = KEYWORD_PLAN_COLUMNS + ["Quick Win Score"]
    ws3 = wb.create_sheet("Quick Wins")
    for col, h in enumerate(quick_headers, 1):
        ws3.cell(row=1, column=col, value=h)
    _apply_header_style(ws3)
    for row_idx, k in enumerate(quick, 2):
        score_val = k.get("quick_win_score")
        row_data = _keyword_plan_row_data(k) + [score_val]
        gsc_label = k.get("gsc_label")
        for col_idx, val in enumerate(row_data, 1):
            cell = ws3.cell(row=row_idx, column=col_idx, value=val)
            cell.font = DATA_FONT
            fill = GSC_LABEL_FILLS.get(gsc_label) if gsc_label else None
            if not fill:
                fill = _row_fill_for_priority(k.get("priority") or "")
            if fill:
                cell.fill = fill
    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = f"A1:{get_column_letter(len(quick_headers))}{ws3.max_row}"
    _auto_column_width(ws3)

    # Sheet 4: Strategie
    notes = strategy_notes or _generate_strategy_metrics(keywords, silos, gsc_connected)
    ws4 = wb.create_sheet("📝 Strategie")
    for row_idx, line in enumerate(notes.split("\n"), 1):
        ws4.cell(row=row_idx, column=1, value=line)
    ws4.column_dimensions["A"].width = 90

    # Sheet 5: Content Gaps
    content_gaps = [k for k in keywords if k.get("gsc_label") == "⬜ Ontbreekt"]
    content_gaps_sorted = sorted(
        content_gaps,
        key=lambda x: (x.get("volume") or 0),
        reverse=True,
    )
    ws5 = wb.create_sheet("Content Gaps")
    ws5.cell(row=1, column=1, value="Content Gaps — geen GSC-ranking (⬜ Ontbreekt); prioriteit met authority-cap (KD>45 zonder ranking → max MEDIUM)")
    for col, h in enumerate(CONTENT_GAPS_COLUMNS, 1):
        ws5.cell(row=2, column=col, value=h)
    _apply_header_style(ws5, row_num=2)
    for row_idx, k in enumerate(content_gaps_sorted, 3):
        raw_p = k.get("priority") or "LOW"
        p = cap_content_gap_priority(
            raw_p,
            k.get("kd"),
            float(k["gsc_position"]) if k.get("gsc_position") is not None else None,
        )
        ws5.cell(row=row_idx, column=1, value=k.get("market") or "NL")
        ws5.cell(row=row_idx, column=2, value=k.get("keyword") or "")
        ws5.cell(row=row_idx, column=3, value=k.get("volume"))
        ws5.cell(row=row_idx, column=4, value=k.get("kd"))
        ws5.cell(row=row_idx, column=5, value=k.get("intent") or "")
        ws5.cell(row=row_idx, column=6, value=k.get("silo") or "")
        ws5.cell(row=row_idx, column=7, value=k.get("content_type") or "")
        ws5.cell(row=row_idx, column=8, value=p)
        for col_idx in range(1, 9):
            cell = ws5.cell(row=row_idx, column=col_idx)
            cell.font = DATA_FONT
    ws5.freeze_panes = "A3"
    ws5.auto_filter.ref = f"A2:{get_column_letter(8)}{ws5.max_row}"
    _auto_column_width(ws5)

    _write_gsc_performance_sheet(wb, gsc_performance, gsc_site_url)
    _write_markt_expansie_sheet(wb, keywords)

    wb.save(filepath)
    logger.info("Generated SEO Excel: %s", filepath)
    return filepath
