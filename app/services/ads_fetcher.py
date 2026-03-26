"""
Google Ads data fetcher voor analytics-comparison jobs.
Wraps fetch_google_ads_via_gaql uit dashboard.py (GAQL gebruikt refresh_token).
Retourneert altijd een gestructureerd dict — nooit een exception naar de caller.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


def _parse_extra(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw.strip() else {}
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


def _enrich_ads_result(
    ads_data: dict[str, Any],
    start_date: str,
    end_date: str,
    extra: dict[str, Any],
) -> dict[str, Any]:
    campaigns = list(ads_data.get("campaigns") or [])
    totals = {
        "spend": sum(float(c.get("cost", 0) or 0) for c in campaigns if isinstance(c, dict)),
        "clicks": sum(int(c.get("clicks", 0) or 0) for c in campaigns if isinstance(c, dict)),
        "impressions": sum(int(c.get("impressions", 0) or 0) for c in campaigns if isinstance(c, dict)),
        "conversions": sum(float(c.get("conversions", 0) or 0) for c in campaigns if isinstance(c, dict)),
    }
    account_name = (
        extra.get("account_name")
        or extra.get("customer_descriptive_name")
        or extra.get("descriptive_name")
        or ""
    )
    return {
        "campaigns": campaigns,
        "timeseries": list(ads_data.get("timeseries") or []),
        "totals": totals,
        "date_range": f"{start_date} — {end_date}",
        "account_name": account_name,
    }


async def fetch_ads_data_for_client(
    db: asyncpg.Connection,
    client_slug: str,
    user_id: str,
    date_range_days: int = 28,
) -> dict[str, Any]:
    """
    Haalt Google Ads data op voor een client via platform-/user-credentials (resolver).

    Returns:
      available, reason (no_credentials | no_campaigns | api_error | token_error), data
    """
    try:
        from app.services.credential_resolver import get_credentials
        from app.services.dashboard import fetch_google_ads_via_gaql, get_valid_access_token

        cred_row = await get_credentials(db, client_slug, "google_ads", user_id=user_id)
        if not cred_row:
            logger.info("ads_fetcher: geen google_ads credentials voor client=%s", client_slug)
            return {"available": False, "reason": "no_credentials", "data": None}

        extra = _parse_extra(cred_row.get("extra_config"))
        refresh_token: Optional[str] = extra.get("refresh_token") or cred_row.get("api_key_encrypted")
        if not refresh_token:
            logger.warning("ads_fetcher: geen refresh_token voor client=%s google_ads", client_slug)
            return {"available": False, "reason": "token_error", "data": None}

        access_token = await get_valid_access_token(db, user_id, client_slug, "google_ads")
        if not access_token:
            logger.warning(
                "ads_fetcher: geen geldig access token (refresh mislukt?) client=%s google_ads",
                client_slug,
            )
            return {"available": False, "reason": "token_error", "data": None}

        customer_id = (
            extra.get("customer_id")
            or extra.get("ads_customer_id")
            or extra.get("account_id")
        )
        if not customer_id:
            logger.warning("ads_fetcher: geen customer_id in extra_config voor client=%s", client_slug)
            return {"available": False, "reason": "no_credentials", "data": None}

        login_customer_id = (
            extra.get("login_customer_id")
            or extra.get("mcc_id")
            or extra.get("manager_customer_id")
        )
        if login_customer_id:
            login_customer_id = str(login_customer_id).replace("-", "").strip() or None

        end_d = date.today()
        start_d = end_d - timedelta(days=max(1, date_range_days) - 1)
        start_date = start_d.isoformat()
        end_date = end_d.isoformat()

        ads_data = await fetch_google_ads_via_gaql(
            refresh_token=refresh_token,
            customer_id=str(customer_id),
            start_date=start_date,
            end_date=end_date,
            login_customer_id=login_customer_id,
        )

        if ads_data.get("not_implemented") or ads_data.get("not_configured"):
            logger.warning(
                "ads_fetcher: Google Ads niet geconfigureerd/geïmplementeerd client=%s keys=%s",
                client_slug,
                list(ads_data.keys()),
            )
            return {"available": False, "reason": "api_error", "data": None}

        if ads_data.get("error"):
            logger.info(
                "ads_fetcher: Google Ads API error client=%s err=%s",
                client_slug,
                ads_data.get("error"),
            )
            return {"available": False, "reason": "api_error", "data": None}

        campaigns = ads_data.get("campaigns") or []
        if not campaigns:
            logger.info("ads_fetcher: lege campaigns van Google Ads voor client=%s", client_slug)
            return {"available": False, "reason": "no_campaigns", "data": None}

        enriched = _enrich_ads_result(ads_data, start_date, end_date, extra)
        logger.info(
            "ads_fetcher: Google Ads data opgehaald voor client=%s — %d campaigns",
            client_slug,
            len(enriched["campaigns"]),
        )
        return {"available": True, "reason": None, "data": enriched}

    except Exception as e:
        logger.error("ads_fetcher: fout bij ophalen Google Ads voor client=%s: %s", client_slug, e)
        return {"available": False, "reason": "api_error", "data": None}
