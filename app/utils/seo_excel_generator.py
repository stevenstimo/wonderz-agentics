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

KEYWORD_PLAN_COLUMNS = [
    "Focus Keyword",
    "Volume",
    "KD",
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


def _filter_quick_wins(keywords: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Position 4-20, volume > 500, KD < 40."""
    return [
        k
        for k in keywords
        if (4 <= (k.get("position") or 0) <= 20)
        and (k.get("volume") or 0) > 500
        and (k.get("kd") or 100) < 40
    ]


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
        f"- {len(quick)} keywords in positie 4-20 met volume > 500 en KD < 40",
        "- Optimaliseer bestaande content voor deze keywords",
        "",
        "## Aanbevolen publicatievolgorde",
        "1. Quick wins eerst (content optimalisatie)",
        "2. HIGH-prioriteit Pillar Pages",
        "3. MEDIUM Landing Pages en Blogs",
    ]
    return "\n".join(lines)


def generate_seo_excel(
    keywords: List[Dict[str, Any]],
    brand_name: str,
    strategy_notes: Optional[str] = None,
) -> str:
    """
    Generate 4-sheet Excel file. Returns path to generated file.
    """
    out_dir = _ensure_output_dir()
    safe_brand = "".join(c if c.isalnum() or c in " -_" else "_" for c in brand_name)[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"SEO_Plan_{safe_brand}_{timestamp}.xlsx"
    filepath = os.path.join(out_dir, filename)

    wb = openpyxl.Workbook()

    # Sheet 1: Keyword Plan
    ws1 = wb.active
    ws1.title = "Keyword Plan"
    for col, header in enumerate(KEYWORD_PLAN_COLUMNS, 1):
        ws1.cell(row=1, column=col, value=header)
    _apply_header_style(ws1)

    for row_idx, k in enumerate(keywords, 2):
        row_data = [
            k.get("keyword", ""),
            k.get("volume", 0),
            k.get("kd", 0),
            k.get("intent", ""),
            k.get("silo", ""),
            k.get("audience_match", ""),
            k.get("content_type", ""),
            k.get("title_suggestion", ""),
            k.get("primary_source", ""),
            "",  # Status — user fills
            "",  # Week — user fills
            k.get("current_url", ""),
            k.get("priority", ""),
        ]
        for col_idx, val in enumerate(row_data, 1):
            cell = ws1.cell(row=row_idx, column=col_idx, value=val)
            cell.font = DATA_FONT
            fill = _row_fill_for_priority(k.get("priority"))
            if fill:
                cell.fill = fill

    ws1.freeze_panes = "A2"
    ws1.auto_filter.ref = ws1.dimensions
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

    # Sheet 3: Quick Wins
    quick = _filter_quick_wins(keywords)
    ws3 = wb.create_sheet("Quick Wins")
    for col, h in enumerate(KEYWORD_PLAN_COLUMNS, 1):
        ws3.cell(row=1, column=col, value=h)
    _apply_header_style(ws3)
    for row_idx, k in enumerate(quick, 2):
        row_data = [
            k.get("keyword", ""),
            k.get("volume", 0),
            k.get("kd", 0),
            k.get("intent", ""),
            k.get("silo", ""),
            k.get("audience_match", ""),
            k.get("content_type", ""),
            k.get("title_suggestion", ""),
            k.get("primary_source", ""),
            "",
            "",
            k.get("current_url", ""),
            k.get("priority", ""),
        ]
        for col_idx, val in enumerate(row_data, 1):
            cell = ws3.cell(row=row_idx, column=col_idx, value=val)
            cell.font = DATA_FONT
    ws3.freeze_panes = "A2"
    _auto_column_width(ws3)

    # Sheet 4: Strategie Notes
    notes = strategy_notes or _generate_strategy_notes(keywords, silos)
    ws4 = wb.create_sheet("Strategie Notes")
    for row_idx, line in enumerate(notes.split("\n"), 1):
        ws4.cell(row=row_idx, column=1, value=line)
    ws4.column_dimensions["A"].width = 80

    wb.save(filepath)
    logger.info("Generated SEO Excel: %s", filepath)
    return filepath
