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
from app.services.credential_resolver import resolve_integration_row

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
            row = await resolve_integration_row(
                conn,
                client_slug=client_slug,
                integration_type="google_search_console",
                user_id=user_id,
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
            row = await resolve_integration_row(
                conn,
                client_slug=client_slug,
                integration_type="google_search_console",
                user_id=user_id,
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

            gsc_by_keyword: dict[str, dict[str, Any]] = {}
            row_limit = 25000
            start_row = 0
            async with httpx.AsyncClient(timeout=120.0) as client:
                while start_row < 250000:
                    payload = {
                        "startDate": start_date,
                        "endDate": end_date,
                        "dimensions": ["query"],
                        "rowLimit": row_limit,
                        "startRow": start_row,
                    }
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code != 200:
                        logger.warning("seo_gsc_fetcher: GSC API error status=%s body=%s", res.status_code, (res.text or "")[:300])
                        if start_row == 0:
                            return empty
                        break
                    data = res.json()
                    batch_rows = data.get("rows", []) or []
                    for row in batch_rows:
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
                    if len(batch_rows) < row_limit:
                        break
                    start_row += row_limit

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
                        "clicks": None,
                        "impressions": None,
                        "ctr": None,
                    }
            return (result, site_url)

    except Exception as e:
        logger.exception("seo_gsc_fetcher: error for user_id=%s client_slug=%s: %s", user_id, client_slug, e)
        return empty


async def fetch_gsc_performance_summary(
    user_id: str,
    client_slug: str,
    days: int = 90,
) -> tuple[dict[str, Any], str | None]:
    """
    Top queries, pages, countries, and daily clicks/impressions for the GSC Performance Excel tab.
    Returns (payload, site_url) or ({}, None) when GSC is unavailable.
    """
    empty: dict[str, Any] = {}
    if not user_id or not client_slug:
        return {}, None

    pool = await init_db_pool()
    if not pool:
        return {}, None

    try:
        async with pool.acquire() as conn:
            row = await resolve_integration_row(
                conn,
                client_slug=client_slug,
                integration_type="google_search_console",
                user_id=user_id,
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
                return {}, None

            access_token = await get_valid_access_token(conn, user_id, client_slug, "google_search_console")
            if not access_token:
                return {}, None

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        site_encoded = urllib.parse.quote(site_url, safe="")
        api_url = f"{GSC_BASE_URL}/sites/{site_encoded}/searchAnalytics/query"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        top_queries: list[dict[str, Any]] = []
        top_pages: list[dict[str, Any]] = []
        countries: list[dict[str, Any]] = []
        timeseries: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:

            async def _post(dimensions: list[str], row_limit: int) -> list[dict[str, Any]]:
                body: dict[str, Any] = {
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": dimensions,
                    "rowLimit": row_limit,
                    "startRow": 0,
                }
                res = await client.post(api_url, headers=headers, json=body)
                if res.status_code != 200:
                    return []
                out: list[dict[str, Any]] = []
                for row in res.json().get("rows", []) or []:
                    keys = row.get("keys", [])
                    dim_val = keys[0] if keys else ""
                    out.append({
                        "dim": dim_val,
                        "clicks": int(row.get("clicks", 0)),
                        "impressions": int(row.get("impressions", 0)),
                        "ctr": round(float(row.get("ctr", 0)), 4),
                        "position": round(float(row.get("position", 0)), 1),
                    })
                return out

            q_raw = await _post(["query"], 100)
            for r in q_raw:
                top_queries.append(
                    {
                        "query": r["dim"],
                        "clicks": r["clicks"],
                        "impressions": r["impressions"],
                        "ctr": r["ctr"],
                        "position": r["position"],
                    }
                )
            p_raw = await _post(["page"], 100)
            for r in p_raw:
                top_pages.append(
                    {
                        "page": r["dim"],
                        "clicks": r["clicks"],
                        "impressions": r["impressions"],
                        "ctr": r["ctr"],
                        "position": r["position"],
                    }
                )
            c_raw = await _post(["country"], 50)
            for r in c_raw:
                countries.append(
                    {
                        "country": r["dim"],
                        "clicks": r["clicks"],
                        "impressions": r["impressions"],
                        "ctr": r["ctr"],
                        "position": r["position"],
                    }
                )
            d_raw = await _post(["date"], 90)
            for r in d_raw:
                timeseries.append(
                    {
                        "date": r["dim"],
                        "clicks": r["clicks"],
                        "impressions": r["impressions"],
                    }
                )

        payload = {
            "top_queries": top_queries,
            "top_pages": top_pages,
            "countries": countries,
            "timeseries": timeseries,
            "date_start": start_date,
            "date_end": end_date,
        }
        return payload, site_url

    except Exception as e:
        logger.warning("fetch_gsc_performance_summary: %s", e)
        return {}, None
