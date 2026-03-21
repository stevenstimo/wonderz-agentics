"""
Google PageSpeed Insights API adapter.
Geeft Core Web Vitals + performance score per URL.
Activeren: zet GOOGLE_PAGESPEED_API_KEY in systemd override.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_PAGESPEED_API_KEY", "")
BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
ENABLED = bool(API_KEY)


async def fetch_pagespeed(url: str, strategy: str = "mobile") -> dict:
    """
    Haalt PageSpeed data op voor een URL.
    strategy: 'mobile' of 'desktop'
    Retourneert gestandaardiseerd dict of {"enabled": False, "data": None}.
    """
    if not ENABLED:
        return {"enabled": False, "data": None}

    params = {"url": url, "strategy": strategy, "key": API_KEY}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        categories = raw.get("lighthouseResult", {}).get("categories", {})
        audits = raw.get("lighthouseResult", {}).get("audits", {})

        return {
            "enabled": True,
            "data": {
                "performance_score": round((categories.get("performance", {}).get("score", 0) or 0) * 100),
                "lcp": audits.get("largest-contentful-paint", {}).get("displayValue"),
                "fid": audits.get("max-potential-fid", {}).get("displayValue"),
                "cls": audits.get("cumulative-layout-shift", {}).get("displayValue"),
                "ttfb": audits.get("server-response-time", {}).get("displayValue"),
                "fcp": audits.get("first-contentful-paint", {}).get("displayValue"),
                "speed_index": audits.get("speed-index", {}).get("displayValue"),
                "strategy": strategy,
                "url": url,
            },
        }
    except httpx.HTTPStatusError as e:
        logger.error("PageSpeed API error %s voor %s: %s", e.response.status_code, url, e)
        return {"enabled": True, "data": None, "error": str(e)}
    except Exception as e:
        logger.error("PageSpeed onverwachte fout voor %s: %s", url, e)
        return {"enabled": True, "data": None, "error": str(e)}
