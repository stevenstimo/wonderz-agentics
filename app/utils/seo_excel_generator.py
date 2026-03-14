"""
SEO Plan Excel generator — produces 4-sheet Excel conform Ikaria format.
Uses openpyxl with header styling, priority row colors, frozen panes, auto-filter.
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill(start_color="2D2D2D", end_color="2D2D2D", fill_type="solid")
HEADER_FONT = Font(name="Arial", size=11, bold=True, color="FFFFFF")
HIGH_FILL = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
MEDIUM_FILL = PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid")
DATA_FONT = Font(name="Arial", size=10)
KD_CLIENT_GREEN = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")

# GSC status label row colors (by full label string)
GSC_LABEL_FILLS = {
    "✅ Sterk": PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid"),
    "🟡 Optimaliseer": PatternFill(start_color="FFFDE7", end_color="FFFDE7", fill_type="solid"),
    "🟠 Aanpakken": PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid"),
    "🔴 Zwak": PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid"),
    "⬜ Ontbreekt": PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid"),
}

KEYWORD_PLAN_COLUMNS = [
    "Focus Keyword",
    "Volume",
    "KD",
    "KD-Client",
    "Status (GSC)",
    "Positie (GSC)",
    "Clicks (GSC)",
    "CTR (GSC)",
    "Intent",
    "Silo",
    "Doelgroep",
    "Content Type",
    "Titel",
    "Primaire Bron",
    "Status",
    "Week",
    "URL",
    "Prioriteit",
]

CONTENT_GAPS_COLUMNS = [
    "Focus Keyword",
    "Volume",
    "KD",
    "Intent",
    "Silo",
    "Content Type",
    "Prioriteit",
]


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
    """Aggregate silo stats: name, count, total volume, avg KD, recommended approach."""
    silos: Dict[str, Dict[str, Any]] = {}
    for k in keywords:
        silo = k.get("silo") or "Overig"
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


def _position_for_quick_wins(k: Dict[str, Any]) -> Optional[float]:
    """Use gsc_position if available, else position from CSV."""
    gsc_pos = k.get("gsc_position")
    if gsc_pos is not None:
        return float(gsc_pos) if isinstance(gsc_pos, (int, float)) else None
    pos = k.get("position")
    if pos is not None:
        return float(pos) if isinstance(pos, (int, float)) else None
    return None


def _quick_win_priority_score(k: Dict[str, Any]) -> float:
    """Priority score: volume * (1 - KD/100) / position. Higher = more urgent."""
    pos = _position_for_quick_wins(k)
    if pos is None or pos <= 0:
        return 0.0
    vol = k.get("volume") or 0
    kd = k.get("kd") or 0
    return vol * (1 - kd / 100) / pos


def _filter_quick_wins(keywords: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Position 4-20 (GSC or CSV), volume > 100, KD < 45. Sorted by priority score DESC."""
    result = []
    for k in keywords:
        pos = _position_for_quick_wins(k)
        if pos is None:
            continue
        if 4 <= pos <= 20 and (k.get("volume") or 0) > 100 and (k.get("kd") or 100) < 45:
            k["quick_win_priority"] = _quick_win_priority_score(k)
            result.append(k)
    return sorted(result, key=lambda x: x.get("quick_win_priority") or 0, reverse=True)


def _generate_strategy_notes(keywords: List[Dict[str, Any]], silos: List[Dict]) -> str:
    """AI-style summary — in v1 we use a simple template. # ASSUMPTION: full AI notes in future."""
    high = [k for k in keywords if k.get("priority") == "HIGH"]
    quick = _filter_quick_wins(keywords)
    lines = [
        "## Top prioriteiten",
        f"- {len(high)} HIGH-prioriteit keywords",
        f"- Focus silo's: {', '.join(s['Silo naam'] for s in silos[:5])}",
        "",
        "## Quick wins",
        f"- {len(quick)} keywords in positie 4-20 met volume > 100 en KD < 45",
        "- Optimaliseer bestaande content voor deze keywords",
        "",
        "## Aanbevolen publicatievolgorde",
        "1. Quick wins eerst (content optimalisatie)",
        "2. HIGH-prioriteit Pillar Pages",
        "3. MEDIUM Landing Pages en Blogs",
    ]
    return "\n".join(lines)


def _ctr_display(ctr: Any) -> Any:
    """Format CTR as percentage (e.g. 0.072 -> '7.2%') or empty."""
    if ctr is None:
        return None
    try:
        n = float(ctr)
        if n == 0:
            return None
        return f"{n * 100:.1f}%"
    except (TypeError, ValueError):
        return None


def _keyword_plan_row_data(k: Dict[str, Any]) -> List[Any]:
    """Build row values for Keyword Plan sheet (with GSC columns). Empty = None for missing data."""
    gsc_pos = k.get("gsc_position")
    kd_client = k.get("kd_client")
    gsc_clicks = k.get("gsc_clicks")
    gsc_ctr = k.get("gsc_ctr")
    # Positie (GSC): empty when None or 0 (do not show "0")
    pos_display = (gsc_pos if (gsc_pos is not None and gsc_pos != 0) else None)
    return [
        k.get("keyword") or "",
        k.get("volume") if k.get("volume") is not None else None,
        k.get("kd") if k.get("kd") is not None else None,
        kd_client if kd_client is not None else None,
        k.get("gsc_label") or None,
        pos_display,
        gsc_clicks if (gsc_clicks is not None and pos_display is not None) else None,
        _ctr_display(gsc_ctr) if pos_display is not None else None,
        k.get("intent") or "",
        k.get("silo") or "",
        k.get("audience_match") or "",
        k.get("content_type") or "",
        k.get("title_suggestion") or "",
        k.get("primary_source") or "",
        "",  # Status — user fills
        "",  # Week — user fills
        k.get("current_url") or "",
        k.get("priority") or "",
    ]


def generate_seo_excel(
    keywords: List[Dict[str, Any]],
    brand_name: str,
    strategy_notes: Optional[str] = None,
    gsc_site_url: Optional[str] = None,
) -> str:
    """
    Generate 5-sheet Excel file (Keyword Plan, Silo Overzicht, Quick Wins, Strategie Notes, Content Gaps).
    Returns path to generated file.
    """
    out_dir = _ensure_output_dir()
    safe_brand = "".join(c if c.isalnum() or c in " -_" else "_" for c in brand_name)[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"SEO_Plan_{safe_brand}_{timestamp}.xlsx"
    filepath = os.path.join(out_dir, filename)

    wb = openpyxl.Workbook()

    # Sheet 1: Keyword Plan (row 1 = GSC note, row 2 = headers, row 3+ = data)
    ws1 = wb.active
    ws1.title = "Keyword Plan"
    note = (
        f"GSC data: laatste 90 dagen — {gsc_site_url} | Top 100 positiedrempel"
        if gsc_site_url
        else "GSC kolommen niet beschikbaar (geen GSC koppeling voor deze client)"
    )
    ws1.cell(row=1, column=1, value=note)
    for col, header in enumerate(KEYWORD_PLAN_COLUMNS, 1):
        ws1.cell(row=2, column=col, value=header)
    _apply_header_style(ws1, row_num=2)

    for row_idx, k in enumerate(keywords, 3):
        row_data = _keyword_plan_row_data(k)
        kd_val = k.get("kd")
        kd_client_val = k.get("kd_client")
        gsc_label = k.get("gsc_label")
        for col_idx, val in enumerate(row_data, 1):
            cell = ws1.cell(row=row_idx, column=col_idx, value=val)
            cell.font = DATA_FONT
            # Row fill by GSC label if present
            fill = GSC_LABEL_FILLS.get(gsc_label) if gsc_label else None
            if not fill:
                fill = _row_fill_for_priority(k.get("priority"))
            if fill:
                cell.fill = fill
            # KD-Client cell: green if value < KD
            if col_idx == 4 and kd_client_val is not None and kd_val is not None:
                try:
                    if float(kd_client_val) < float(kd_val):
                        cell.fill = KD_CLIENT_GREEN
                except (TypeError, ValueError):
                    pass

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
    _auto_column_width(ws2)

    # Sheet 3: Quick Wins (Keyword Plan columns + Prioriteit Quick Win, sorted by priority DESC)
    quick = _filter_quick_wins(keywords)
    quick_wins_headers = KEYWORD_PLAN_COLUMNS + ["Prioriteit Quick Win"]
    ws3 = wb.create_sheet("Quick Wins")
    for col, h in enumerate(quick_wins_headers, 1):
        ws3.cell(row=1, column=col, value=h)
    _apply_header_style(ws3)
    for row_idx, k in enumerate(quick, 2):
        priority_val = k.get("quick_win_priority")
        row_data = _keyword_plan_row_data(k) + [
            round(priority_val, 1) if priority_val is not None else None,
        ]
        kd_val = k.get("kd")
        kd_client_val = k.get("kd_client")
        gsc_label = k.get("gsc_label")
        for col_idx, val in enumerate(row_data, 1):
            cell = ws3.cell(row=row_idx, column=col_idx, value=val)
            cell.font = DATA_FONT
            fill = GSC_LABEL_FILLS.get(gsc_label) if gsc_label else None
            if not fill:
                fill = _row_fill_for_priority(k.get("priority"))
            if fill:
                cell.fill = fill
            if col_idx == 4 and kd_client_val is not None and kd_val is not None:
                try:
                    if float(kd_client_val) < float(kd_val):
                        cell.fill = KD_CLIENT_GREEN
                except (TypeError, ValueError):
                    pass
    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = f"A1:{get_column_letter(len(quick_wins_headers))}{ws3.max_row}"
    _auto_column_width(ws3)

    # Sheet 4: Strategie Notes
    notes = strategy_notes or _generate_strategy_notes(keywords, silos)
    ws4 = wb.create_sheet("Strategie Notes")
    for row_idx, line in enumerate(notes.split("\n"), 1):
        ws4.cell(row=row_idx, column=1, value=line)
    ws4.column_dimensions["A"].width = 80

    # Sheet 5: Content Gaps (keywords not found in GSC)
    content_gaps = [k for k in keywords if k.get("gsc_label") == "⬜ Ontbreekt"]
    content_gaps_sorted = sorted(
        content_gaps,
        key=lambda x: x.get("volume") or 0,
        reverse=True,
    )
    ws5 = wb.create_sheet("Content Gaps")
    ws5.cell(row=1, column=1, value="Content Gaps — Keywords niet gevonden in Google Search Console")
    ws5.cell(row=2, column=1, value="Dit zijn keywords waarop de site nog geen zichtbaarheid heeft. Hoog volume + lage KD = hoogste prioriteit voor nieuwe content.")
    for col, h in enumerate(CONTENT_GAPS_COLUMNS, 1):
        ws5.cell(row=3, column=col, value=h)
    _apply_header_style(ws5, row_num=3)
    for row_idx, k in enumerate(content_gaps_sorted, 4):
        vol = k.get("volume")
        kd = k.get("kd")
        ws5.cell(row=row_idx, column=1, value=k.get("keyword") or "")
        ws5.cell(row=row_idx, column=2, value=vol if vol is not None else None)
        ws5.cell(row=row_idx, column=3, value=kd if kd is not None else None)
        ws5.cell(row=row_idx, column=4, value=k.get("intent") or "")
        ws5.cell(row=row_idx, column=5, value=k.get("silo") or "")
        ws5.cell(row=row_idx, column=6, value=k.get("content_type") or "")
        ws5.cell(row=row_idx, column=7, value=k.get("priority") or "")
        for col_idx in range(1, 8):
            cell = ws5.cell(row=row_idx, column=col_idx)
            cell.font = DATA_FONT
    ws5.freeze_panes = "A4"
    ws5.auto_filter.ref = f"A3:{get_column_letter(7)}{ws5.max_row}"
    _auto_column_width(ws5)

    wb.save(filepath)
    logger.info("Generated SEO Excel: %s", filepath)
    return filepath
