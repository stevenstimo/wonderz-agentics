"""
SEO Tool — GSC data fetcher for keyword enrichment.
Fetches Search Console query data (position, clicks, impressions, CTR) for a list of keywords.
Uses client_integrations (google_search_console) for token and site_url; fallback to client_platform_configs (gsc).
On missing config or API errors, returns {} so the SEO job continues without GSC columns.
"""
import json
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.db import init_db_pool
from app.services.dashboard import get_valid_access_token

logger = logging.getLogger(__name__)

GSC_BASE_URL = "https://www.googleapis.com/webmasters/v3"


def _get_site_url_from_row(row: Any, config_key: str) -> str | None:
    """Extract site_url from extra_config or config (dict or JSON string)."""
    if not row or not row.get(config_key):
        return None
    extra = row[config_key]
    if isinstance(extra, dict) and extra.get("site_url"):
        return extra["site_url"]
    if isinstance(extra, str):
        try:
            data = json.loads(extra)
            if isinstance(data, dict) and data.get("site_url"):
                return data["site_url"]
        except Exception:
            pass
    return None


async def get_gsc_site_url_for_client(user_id: str, client_slug: str) -> str | None:
    """
    Resolve GSC site_url for a client (for domain display / Excel note).
    Same lookup order as fetch_gsc_for_keywords: client_integrations then client_platform_configs.
    """
    if not user_id or not client_slug:
        return None
    pool = await init_db_pool()
    if not pool:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT extra_config FROM client_integrations
                WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'google_search_console'
                """,
                user_id,
                client_slug,
            )
            site_url = _get_site_url_from_row(row, "extra_config") if row else None
            if not site_url:
                row = await conn.fetchrow(
                    """
                    SELECT config FROM client_platform_configs
                    WHERE user_id = $1 AND client_slug = $2 AND platform = 'gsc'
                    """,
                    user_id,
                    client_slug,
                )
                site_url = _get_site_url_from_row(row, "config") if row else None
            return site_url
    except Exception as e:
        logger.warning("get_gsc_site_url_for_client: %s", e)
        return None


async def fetch_gsc_for_keywords(
    user_id: str,
    client_slug: str,
    keywords: list[str],
    days: int = 90,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    """
    Fetch GSC data for a list of keywords.

    Returns (data, site_url).
    - data: dict keyed by original keyword string; each value has position, clicks, impressions, ctr.
    - site_url: the GSC site URL used (for Excel note), or None if no data.

    On no GSC config, no token, or API error: returns ({}, None).
    """
    empty = ({}, None)
    if not user_id or not client_slug or not keywords:
        return empty

    pool = await init_db_pool()
    if not pool:
        logger.warning("seo_gsc_fetcher: no DB pool")
        return empty

    try:
        async with pool.acquire() as conn:
            # 1) site_url: first client_integrations.extra_config->>'site_url' for google_search_console
            row = await conn.fetchrow(
                """
                SELECT extra_config FROM client_integrations
                WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'google_search_console'
                """,
                user_id,
                client_slug,
            )
            site_url: str | None = None
            if row and row.get("extra_config"):
                extra = row["extra_config"]
                if isinstance(extra, dict) and extra.get("site_url"):
                    site_url = extra.get("site_url")
                elif isinstance(extra, str):
                    try:
                        data = json.loads(extra)
                        if isinstance(data, dict) and data.get("site_url"):
                            site_url = data["site_url"]
                    except Exception:
                        pass

            if not site_url:
                row = await conn.fetchrow(
                    """
                    SELECT config FROM client_platform_configs
                    WHERE user_id = $1 AND client_slug = $2 AND platform = 'gsc'
                    """,
                    user_id,
                    client_slug,
                )
                if row and row.get("config"):
                    cfg = row["config"]
                    if isinstance(cfg, dict) and cfg.get("site_url"):
                        site_url = cfg["site_url"]
                    elif isinstance(cfg, str):
                        try:
                            data = json.loads(cfg)
                            if isinstance(data, dict) and data.get("site_url"):
                                site_url = data["site_url"]
                        except Exception:
                            pass

            if not site_url:
                logger.info("seo_gsc_fetcher: no site_url for user_id=%s client_slug=%s", user_id, client_slug)
                return empty

            access_token = await get_valid_access_token(conn, user_id, client_slug, "google_search_console")
            if not access_token:
                logger.info("seo_gsc_fetcher: no valid token for user_id=%s client_slug=%s", user_id, client_slug)
                return empty

            site_encoded = urllib.parse.quote(site_url, safe="")
            url = f"{GSC_BASE_URL}/sites/{site_encoded}/searchAnalytics/query"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            payload = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["query"],
                "rowLimit": 1000,
                "startRow": 0,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code != 200:
                    logger.warning("seo_gsc_fetcher: GSC API error status=%s body=%s", res.status_code, (res.text or "")[:300])
                    return empty
                data = res.json()

            gsc_by_keyword: dict[str, dict[str, Any]] = {}
            for row in data.get("rows", []):
                keys = row.get("keys", [])
                query = (keys[0] or "").lower().strip() if keys else ""
                if not query:
                    continue
                gsc_by_keyword[query] = {
                    "position": round(float(row.get("position", 0)), 1),
                    "clicks": int(row.get("clicks", 0)),
                    "impressions": int(row.get("impressions", 0)),
                    "ctr": round(float(row.get("ctr", 0)), 3),
                }

            # Match to requested keywords (case-insensitive), keep original keyword as key
            result: dict[str, dict[str, Any]] = {}
            for kw in keywords:
                kw_lower = (kw or "").lower().strip()
                hit = gsc_by_keyword.get(kw_lower)
                if hit:
                    result[kw] = {
                        "position": hit["position"],
                        "clicks": hit["clicks"],
                        "impressions": hit["impressions"],
                        "ctr": hit["ctr"],
                    }
                else:
                    result[kw] = {
                        "position": None,
                        "clicks": 0,
                        "impressions": 0,
                        "ctr": 0,
                    }
            return (result, site_url)

    except Exception as e:
        logger.exception("seo_gsc_fetcher: error for user_id=%s client_slug=%s: %s", user_id, client_slug, e)
        return empty
