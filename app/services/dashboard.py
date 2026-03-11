"""Marketing Dashboard service — fetches GA4, Google Ads, GSC data via OAuth tokens."""

import json
import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

import httpx

from app.core.config import (
    GOOGLE_ADS_DEVELOPER_TOKEN,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
)

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GA4_RUN_REPORT_URL = "https://analyticsdata.googleapis.com/v1beta"
GA4_ADMIN_URL = "https://analyticsadmin.googleapis.com/v1beta"
GSC_BASE_URL = "https://www.googleapis.com/webmasters/v3"


async def _refresh_access_token(refresh_token: str) -> Optional[str]:
    """Exchange refresh_token for access_token."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        logger.warning("Google OAuth not configured")
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
        },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        logger.warning(f"Token refresh failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    return data.get("access_token")


async def list_ga4_properties(access_token: str) -> list[dict[str, str]]:
    """List all GA4 properties accessible via the token. Returns [{ property_id, display_name }]."""
    url = f"{GA4_ADMIN_URL}/accountSummaries"
    headers = {"Authorization": f"Bearer {access_token}"}
    result: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers=headers)
    if r.status_code != 200:
        err_body = r.text[:500] if r.text else ""
        logger.warning(
            "GA4 properties API error: status=%s body=%s",
            r.status_code,
            err_body,
        )
        raise PermissionError(f"GA4 API error: {r.status_code} — {err_body}")
    data = r.json()
    for acc in data.get("accountSummaries", []):
        for prop in acc.get("propertySummaries", []):
            name = prop.get("property", "")
            if name.startswith("properties/"):
                pid = name.replace("properties/", "")
                display = prop.get("displayName", pid)
                result.append({"property_id": pid, "display_name": display})
    return result


async def list_gsc_sites(access_token: str) -> list[dict[str, str]]:
    """List all GSC sites accessible via the token. Returns [{ site_url, permission_level }]."""
    url = f"{GSC_BASE_URL}/sites"
    headers = {"Authorization": f"Bearer {access_token}"}
    result: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers=headers)
    if r.status_code != 200:
        err_body = r.text[:500] if r.text else ""
        logger.warning("GSC sites API error: status=%s body=%s", r.status_code, err_body)
        raise PermissionError(f"GSC API error: {r.status_code} — {err_body}")
    data = r.json()
    for entry in data.get("siteEntry", []):
        site_url = entry.get("siteUrl")
        perm = entry.get("permissionLevel", "")
        if site_url:
            result.append({"site_url": site_url, "permission_level": perm})
    return result


def _format_customer_id(cid: str) -> str:
    """Format 1234567890 as 123-456-7890."""
    cid = cid.replace("-", "")
    if len(cid) >= 10:
        return f"{cid[:3]}-{cid[3:6]}-{cid[6:]}"
    return cid


async def list_google_ads_accounts(refresh_token: str) -> list[dict[str, str]]:
    """List all Google Ads accounts accessible via the token. Returns [{ customer_id, descriptive_name }]."""
    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        raise RuntimeError("google-ads package not installed")
    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN]):
        raise RuntimeError("GOOGLE_ADS_DEVELOPER_TOKEN not configured")
    config = {
        "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    try:
        client = GoogleAdsClient.load_from_dict(config)
        customer_service = client.get_service("CustomerService")
        response = customer_service.list_accessible_customers()
        result: list[dict[str, str]] = []
        for resource_name in response.resource_names:
            if not resource_name.startswith("customers/"):
                continue
            cid = resource_name.replace("customers/", "")
            desc = _format_customer_id(cid)
            try:
                customer = customer_service.get_customer(resource_name=resource_name)
                desc = getattr(customer, "descriptive_name", None) or desc
            except (GoogleAdsException, Exception):
                pass
            result.append({"customer_id": cid, "descriptive_name": desc})
        return result
    except Exception as e:
        logger.warning(f"List Google Ads accounts failed: {e}")
        raise PermissionError(str(e)) from e


async def _get_first_gsc_site(access_token: str) -> Optional[str]:
    """List GSC sites and return the first site URL."""
    url = f"{GSC_BASE_URL}/sites"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    for entry in data.get("siteEntry", []):
        site_url = entry.get("siteUrl")
        if site_url:
            return site_url
    return None


async def _get_first_ga4_property(access_token: str) -> Optional[str]:
    """List GA4 properties and return the first property ID (numeric part)."""
    url = f"{GA4_ADMIN_URL}/accountSummaries"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    for acc in data.get("accountSummaries", []):
        for prop in acc.get("propertySummaries", []):
            name = prop.get("property", "")
            if name.startswith("properties/"):
                return name.replace("properties/", "")
    return None


async def _get_first_google_ads_customer(refresh_token: str) -> Optional[str]:
    """List accessible Google Ads customers and return the first (numeric ID)."""
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError:
        return None
    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN]):
        return None
    config = {
        "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    try:
        client = GoogleAdsClient.load_from_dict(config)
        customer_service = client.get_service("CustomerService")
        response = customer_service.list_accessible_customers()
        for name in response.resource_names:
            if name.startswith("customers/"):
                return name.replace("customers/", "")
    except Exception as e:
        logger.warning(f"List accessible customers failed: {e}")
    return None


def _get_refresh_token(api_key_encrypted: Optional[str], extra_config: Optional[dict]) -> Optional[str]:
    """Extract refresh_token from integration row."""
    if isinstance(extra_config, str):
        try:
            extra_config = json.loads(extra_config)
        except Exception:
            extra_config = {}
    extra = extra_config or {}
    refresh = extra.get("refresh_token")
    if refresh:
        return refresh
    # Fallback: api_key_encrypted may store refresh_token when no extra_config
    return api_key_encrypted


async def fetch_ga4(
    access_token: str,
    property_id: str,
    start_date: str,
    end_date: str,
    channel_filter: Optional[str] = None,
    device_filter: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch GA4 metrics: users, sessions, conversions, conversion rate, traffic per channel."""
    url = f"{GA4_RUN_REPORT_URL}/properties/{property_id}:runReport"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    # Build dimension/metric filters
    dimension_filter = None
    if channel_filter or device_filter:
        exprs = []
        if channel_filter:
            exprs.append({
                "filter": {
                    "fieldName": "sessionDefaultChannelGroup",
                    "stringFilter": {"matchType": "EXACT", "value": channel_filter},
                },
            })
        if device_filter:
            exprs.append({
                "filter": {
                    "fieldName": "deviceCategory",
                    "stringFilter": {"matchType": "EXACT", "value": device_filter},
                },
            })
        if len(exprs) == 1:
            dimension_filter = {"filter": exprs[0]["filter"]}
        elif len(exprs) > 1:
            dimension_filter = {"andGroup": {"expressions": exprs}}

    # 1. Overview metrics (no dimensions)
    overview_body = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "metrics": [
            {"name": "activeUsers"},
            {"name": "sessions"},
            {"name": "conversions"},
            {"name": "totalRevenue"},
            {"name": "engagementRate"},
        ],
    }
    if dimension_filter:
        overview_body["dimensionFilter"] = dimension_filter

    # 2. Time series (date dimension)
    timeseries_body = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensions": [{"name": "date"}],
        "metrics": [
            {"name": "activeUsers"},
            {"name": "sessions"},
            {"name": "conversions"},
            {"name": "totalRevenue"},
        ],
    }
    if dimension_filter:
        timeseries_body["dimensionFilter"] = dimension_filter

    # 3. Traffic by channel
    channel_body = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensions": [{"name": "sessionDefaultChannelGroup"}],
        "metrics": [
            {"name": "activeUsers"},
            {"name": "sessions"},
            {"name": "conversions"},
        ],
        "limit": 15,
    }

    result: dict[str, Any] = {
        "kpis": {},
        "timeseries": [],
        "traffic_by_channel": [],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Overview
        r = await client.post(url, headers=headers, json=overview_body)
        if r.status_code != 200:
            logger.warning(f"GA4 overview failed: {r.status_code} {r.text}")
            return result
        data = r.json()
        rows = data.get("rows", [])
        if rows:
            row = rows[0]
            metrics = row.get("metricValues", [])
            result["kpis"] = {
                "users": int(metrics[0].get("value", 0)) if len(metrics) > 0 else 0,
                "sessions": int(metrics[1].get("value", 0)) if len(metrics) > 1 else 0,
                "conversions": float(metrics[2].get("value", 0)) if len(metrics) > 2 else 0,
                "conversion_value": float(metrics[3].get("value", 0)) if len(metrics) > 3 else 0,
                "engagement_rate": float(metrics[4].get("value", 0)) if len(metrics) > 4 else 0,
            }
            if result["kpis"]["sessions"] > 0:
                result["kpis"]["conversion_rate"] = (
                    result["kpis"]["conversions"] / result["kpis"]["sessions"] * 100
                )
            else:
                result["kpis"]["conversion_rate"] = 0.0

        # Time series
        r = await client.post(url, headers=headers, json=timeseries_body)
        if r.status_code == 200:
            data = r.json()
            for row in data.get("rows", []):
                dims = row.get("dimensionValues", [])
                metrics = row.get("metricValues", [])
                if dims and metrics:
                    result["timeseries"].append({
                        "date": dims[0].get("value", ""),
                        "users": int(metrics[0].get("value", 0)) if len(metrics) > 0 else 0,
                        "sessions": int(metrics[1].get("value", 0)) if len(metrics) > 1 else 0,
                        "conversions": float(metrics[2].get("value", 0)) if len(metrics) > 2 else 0,
                        "conversion_value": float(metrics[3].get("value", 0)) if len(metrics) > 3 else 0,
                    })

        # Traffic by channel
        r = await client.post(url, headers=headers, json=channel_body)
        if r.status_code == 200:
            data = r.json()
            for row in data.get("rows", []):
                dims = row.get("dimensionValues", [])
                metrics = row.get("metricValues", [])
                if dims and metrics:
                    result["traffic_by_channel"].append({
                        "channel": dims[0].get("value", "(not set)"),
                        "users": int(metrics[0].get("value", 0)) if len(metrics) > 0 else 0,
                        "sessions": int(metrics[1].get("value", 0)) if len(metrics) > 1 else 0,
                        "conversions": float(metrics[2].get("value", 0)) if len(metrics) > 2 else 0,
                    })

    return result


async def fetch_google_ads_via_gaql(
    refresh_token: str,
    customer_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Fetch Google Ads via GAQL using google-ads library."""
    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        return {"not_implemented": True, "campaigns": [], "timeseries": []}

    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN]):
        return {"not_configured": True, "campaigns": [], "timeseries": []}

    config = {
        "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    try:
        client = GoogleAdsClient.load_from_dict(config)
    except Exception as e:
        logger.warning(f"Google Ads client init failed: {e}")
        return {"error": str(e), "campaigns": [], "timeseries": []}

    # Normalize customer_id: 123-456-7890 -> 1234567890
    cid = customer_id.replace("-", "")

    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          metrics.clicks,
          metrics.impressions,
          metrics.conversions,
          metrics.conversions_value,
          metrics.cost_micros
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND campaign.status = 'ENABLED'
    """
    campaigns: list[dict] = []
    try:
        stream = ga_service.search_stream(customer_id=cid, query=query)
        for batch in stream:
            for row in batch.results:
                m = row.metrics
                conv_val = getattr(m, "conversions_value", 0) or 0
                cost = (getattr(m, "cost_micros", 0) or 0) / 1_000_000
                conv = getattr(m, "conversions", 0) or 0
                cpa = cost / conv if conv else 0
                campaigns.append({
                    "campaign_id": row.campaign.id,
                    "campaign_name": row.campaign.name,
                    "clicks": getattr(m, "clicks", 0) or 0,
                    "impressions": getattr(m, "impressions", 0) or 0,
                    "conversions": conv,
                    "conversion_value": conv_val,
                    "cost": cost,
                    "cpa": cpa,
                })
    except GoogleAdsException as ex:
        logger.warning(f"Google Ads query failed: {ex}")
        return {"error": str(ex), "campaigns": campaigns, "timeseries": []}

    # Time series: cost per day
    query_ts = f"""
        SELECT
          segments.date,
          metrics.cost_micros,
          metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND campaign.status = 'ENABLED'
    """
    timeseries: list[dict] = []
    try:
        stream = ga_service.search_stream(customer_id=cid, query=query_ts)
        by_date: dict[str, dict] = {}
        for batch in stream:
            for row in batch.results:
                d = row.segments.date
                m = row.metrics
                cost = (getattr(m, "cost_micros", 0) or 0) / 1_000_000
                conv = getattr(m, "conversions", 0) or 0
                if d not in by_date:
                    by_date[d] = {"date": d, "cost": 0, "conversions": 0}
                by_date[d]["cost"] += cost
                by_date[d]["conversions"] += conv
        timeseries = sorted(by_date.values(), key=lambda x: x["date"])
    except GoogleAdsException:
        pass

    return {"campaigns": campaigns, "timeseries": timeseries}


async def fetch_gsc(
    access_token: str,
    site_url: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Fetch Search Console: clicks, impressions, CTR, position, top queries, top pages."""
    # Site URL must be URL-encoded for the path
    import urllib.parse
    site_encoded = urllib.parse.quote(site_url, safe="")
    url = f"{GSC_BASE_URL}/sites/{site_encoded}/searchAnalytics/query"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    result: dict[str, Any] = {
        "totals": {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0},
        "top_queries": [],
        "top_pages": [],
        "timeseries": [],
    }

    # 1. Totals (no dimensions)
    body = {
        "startDate": start_date,
        "endDate": end_date,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=body)
        if r.status_code != 200:
            logger.warning(f"GSC totals failed: {r.status_code} {r.text}")
            return result
        data = r.json()
        rows = data.get("rows", [])
        if rows:
            row = rows[0]
            result["totals"] = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0),
                "position": row.get("position", 0),
            }

        # 2. Top queries
        body_query = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "rowLimit": 10,
        }
        r = await client.post(url, headers=headers, json=body_query)
        if r.status_code == 200:
            data = r.json()
            for row in data.get("rows", []):
                keys = row.get("keys", [])
                result["top_queries"].append({
                    "query": keys[0] if keys else "(not set)",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0),
                    "position": row.get("position", 0),
                })

        # 3. Top pages
        body_page = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page"],
            "rowLimit": 10,
        }
        r = await client.post(url, headers=headers, json=body_page)
        if r.status_code == 200:
            data = r.json()
            for row in data.get("rows", []):
                keys = row.get("keys", [])
                result["top_pages"].append({
                    "page": keys[0] if keys else "(not set)",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0),
                    "position": row.get("position", 0),
                })

        # 4. Time series (clicks per day)
        body_ts = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date"],
        }
        r = await client.post(url, headers=headers, json=body_ts)
        if r.status_code == 200:
            data = r.json()
            for row in data.get("rows", []):
                keys = row.get("keys", [])
                result["timeseries"].append({
                    "date": keys[0] if keys else "",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                })

    return result
