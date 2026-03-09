"""
SEO Keyword CSV/XLSX parser — parses Semrush-style exports into keyword dicts.
Required columns: Keyword, Search Volume, Keyword Difficulty.
Optional: Position, CPC, URL, Keyword Intents.
"""
import csv
import io
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Column name mappings (case-insensitive, various export formats)
VOLUME_ALIASES = ("search volume", "volume", "sv", "search_volume", "monthly volume")
KD_ALIASES = ("keyword difficulty", "kd", "keyword_difficulty", "difficulty")
KEYWORD_ALIASES = ("keyword", "keywords", "query", "zoekwoord")
POSITION_ALIASES = ("position", "pos", "rank", "current position")
CPC_ALIASES = ("cpc", "cost per click", "cost-per-click")
URL_ALIASES = ("url", "current url", "landing page")
INTENT_ALIASES = ("keyword intents", "intent", "keyword_intents", "intents")


def _normalize_header(h: str) -> str:
    return (h or "").strip().lower()


def _find_column(headers: List[str], aliases: tuple) -> Optional[int]:
    for i, h in enumerate(headers):
        if _normalize_header(h) in aliases:
            return i
    return None


def parse_csv(content: bytes) -> List[Dict[str, Any]]:
    """Parse CSV content into list of keyword dicts."""
    text = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    headers = [str(h).strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        elif len(row) > len(headers):
            row = row[: len(headers)]
        data.append(dict(zip(headers, row)))
    return _normalize_rows(data)


def parse_xlsx(content: bytes) -> List[Dict[str, Any]]:
    """Parse XLSX content (first sheet) into list of keyword dicts."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = wb.active
    if not sheet:
        return []
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h or "").strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        row_values = [str(c) if c is not None else "" for c in row]
        if len(row_values) < len(headers):
            row_values = row_values + [""] * (len(headers) - len(row_values))
        elif len(row_values) > len(headers):
            row_values = row_values[: len(headers)]
        data.append(dict(zip(headers, row_values)))
    wb.close()
    return _normalize_rows(data)


def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map various column names to standard keys and coerce types."""
    if not rows:
        return []
    headers = list(rows[0].keys())
    kw_idx = _find_column(headers, KEYWORD_ALIASES)
    vol_idx = _find_column(headers, VOLUME_ALIASES)
    kd_idx = _find_column(headers, KD_ALIASES)
    pos_idx = _find_column(headers, POSITION_ALIASES)
    cpc_idx = _find_column(headers, CPC_ALIASES)
    url_idx = _find_column(headers, URL_ALIASES)
    intent_idx = _find_column(headers, INTENT_ALIASES)

    if kw_idx is None:
        raise ValueError("Required column 'Keyword' not found")
    if vol_idx is None:
        raise ValueError("Required column 'Search Volume' not found")
    if kd_idx is None:
        raise ValueError("Required column 'Keyword Difficulty' not found")

    kw_col = headers[kw_idx]
    vol_col = headers[vol_idx]
    kd_col = headers[kd_idx]
    pos_col = headers[pos_idx] if pos_idx is not None else None
    cpc_col = headers[cpc_idx] if cpc_idx is not None else None
    url_col = headers[url_idx] if url_idx is not None else None
    intent_col = headers[intent_idx] if intent_idx is not None else None

    result = []
    for r in rows:
        kw = (r.get(kw_col) or "").strip()
        if not kw:
            continue
        vol_raw = r.get(vol_col) or "0"
        kd_raw = r.get(kd_col) or "0"
        try:
            vol = int(float(str(vol_raw).replace(",", "").replace(" ", "")))
        except (ValueError, TypeError):
            vol = 0
        try:
            kd = float(str(kd_raw).replace(",", ".").replace(" ", ""))
        except (ValueError, TypeError):
            kd = 0.0

        pos = None
        if pos_col and r.get(pos_col):
            try:
                pos = int(float(str(r.get(pos_col)).replace(",", "")))
            except (ValueError, TypeError):
                pass

        cpc = None
        if cpc_col and r.get(cpc_col):
            try:
                cpc = float(str(r.get(cpc_col)).replace(",", "."))
            except (ValueError, TypeError):
                pass

        url = (r.get(url_col) or "").strip() if url_col else None
        intent = (r.get(intent_col) or "").strip() if intent_col else None

        result.append({
            "keyword": kw,
            "volume": vol,
            "kd": kd,
            "position": pos,
            "cpc": cpc,
            "current_url": url or None,
            "intent": intent or None,
        })
    return result


def parse_keywords_file(content: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parse CSV or XLSX file into keyword list.
    Raises ValueError on missing required columns or invalid format.
    """
    ext = (filename or "").lower().split(".")[-1] if "." in (filename or "") else ""
    if ext == "csv":
        return parse_csv(content)
    if ext in ("xlsx", "xls"):
        return parse_xlsx(content)
    raise ValueError(f"Unsupported file type: .{ext}. Use CSV or XLSX.")
