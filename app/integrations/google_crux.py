"""
Chrome UX Report (CrUX) API adapter.
Geeft real-world laadtijddata van echte Chrome-gebruikers.
Activeren: zet GOOGLE_CRUX_API_KEY in systemd override.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_CRUX_API_KEY", "")
BASE_URL = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
ENABLED = bool(API_KEY)


async def fetch_crux(origin: str, form_factor: str = "PHONE") -> dict:
    """
    Haalt CrUX data op voor een origin (bijv. https://example.com).
    form_factor: 'PHONE', 'DESKTOP', 'TABLET'
    """
    if not ENABLED:
        return {"enabled": False, "data": None}

    payload = {"origin": origin, "formFactor": form_factor}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{BASE_URL}?key={API_KEY}",
                json=payload,
            )
            resp.raise_for_status()
            raw = resp.json()

        metrics = raw.get("record", {}).get("metrics", {})

        def p75(metric_key: str):
            m = metrics.get(metric_key, {})
            return m.get("percentiles", {}).get("p75")

        return {
            "enabled": True,
            "data": {
                "origin": origin,
                "form_factor": form_factor,
                "lcp_p75": p75("largest_contentful_paint"),
                "fid_p75": p75("first_input_delay"),
                "cls_p75": p75("cumulative_layout_shift"),
                "inp_p75": p75("interaction_to_next_paint"),
                "ttfb_p75": p75("experimental_time_to_first_byte"),
                "fcp_p75": p75("first_contentful_paint"),
            },
        }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"enabled": True, "data": None, "error": "no_data"}
        logger.error("CrUX API error %s voor %s: %s", e.response.status_code, origin, e)
        return {"enabled": True, "data": None, "error": str(e)}
    except Exception as e:
        logger.error("CrUX onverwachte fout voor %s: %s", origin, e)
        return {"enabled": True, "data": None, "error": str(e)}
