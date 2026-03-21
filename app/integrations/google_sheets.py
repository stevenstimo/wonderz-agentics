"""
Google Sheets API adapter.
Leest briefs en contentkalenders in vanuit Google Sheets per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"


async def read_sheet(access_token: str, spreadsheet_id: str, range_: str = "Sheet1!A1:Z1000") -> dict:
    """
    Leest een bereik uit een Google Sheet.
    range_: bijv. 'Sheet1!A1:Z100' of 'Contentkalender!A:F'
    """
    try:
        from urllib.parse import quote

        range_encoded = quote(range_, safe="")
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{spreadsheet_id}/values/{range_encoded}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

        values = raw.get("values", [])
        if not values:
            return {"enabled": True, "data": {"headers": [], "rows": []}}

        headers = values[0] if values else []
        rows = []
        for row in values[1:]:
            padded = row + [""] * (len(headers) - len(row))
            rows.append(dict(zip(headers, padded)))

        return {
            "enabled": True,
            "data": {
                "spreadsheet_id": spreadsheet_id,
                "range": range_,
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
            },
        }
    except Exception as e:
        logger.error("Sheets API fout voor %s: %s", spreadsheet_id, e)
        return {"enabled": True, "data": None, "error": str(e)}
