"""
Google Sheets API adapter.
Leest briefs en contentkalenders in vanuit Google Sheets per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"


async def get_spreadsheet(access_token: str, spreadsheet_id: str) -> dict:
    """Spreadsheet metadata (titel, sheets)."""
    try:
        sid = spreadsheet_id.strip()
        fields = "properties.title,properties.locale,sheets.properties"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{sid}",
                params={"fields": fields},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()
        return {
            "enabled": True,
            "data": {
                "spreadsheet_id": sid,
                "title": (raw.get("properties") or {}).get("title"),
                "locale": (raw.get("properties") or {}).get("locale"),
                "sheets": [
                    {"sheet_id": (s.get("properties") or {}).get("sheetId"), "title": (s.get("properties") or {}).get("title")}
                    for s in raw.get("sheets", [])
                ],
            },
        }
    except Exception as e:
        logger.error("Sheets metadata fout voor %s: %s", spreadsheet_id, e)
        return {"enabled": True, "data": None, "error": str(e)}


async def get_values(access_token: str, spreadsheet_id: str, range_: str = "Sheet1!A1:Z1000") -> dict:
    """Celwaarden uit een bereik (A1-notatie)."""
    try:
        sid = spreadsheet_id.strip()
        range_encoded = quote(range_, safe="")
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{sid}/values/{range_encoded}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

        values = raw.get("values", [])
        if not values:
            return {"enabled": True, "data": {"spreadsheet_id": sid, "range": range_, "headers": [], "rows": []}}

        headers = values[0] if values else []
        rows = []
        for row in values[1:]:
            padded = row + [""] * (len(headers) - len(row))
            rows.append(dict(zip(headers, padded)))

        return {
            "enabled": True,
            "data": {
                "spreadsheet_id": sid,
                "range": range_,
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
            },
        }
    except Exception as e:
        logger.error("Sheets values fout voor %s: %s", spreadsheet_id, e)
        return {"enabled": True, "data": None, "error": str(e)}


async def read_sheet(access_token: str, spreadsheet_id: str, range_: str = "Sheet1!A1:Z1000") -> dict:
    """Leest een bereik uit een Google Sheet (backward compat)."""
    return await get_values(access_token, spreadsheet_id, range_)


class GoogleSheetsAdapter:
    get_spreadsheet = staticmethod(get_spreadsheet)
    get_values = staticmethod(get_values)
    read_sheet = staticmethod(read_sheet)
