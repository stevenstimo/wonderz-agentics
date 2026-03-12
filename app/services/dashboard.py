"""Marketing Dashboard service — fetches GA4, Google Ads, GSC data via OAuth tokens."""

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Optional, Tuple

import httpx

from app.core.config import (
    GOOGLE_ADS_DEVELOPER_TOKEN,
    GOOGLE_ADS_LOGIN_CUSTOMER_ID,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
)

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GA4_RUN_REPORT_URL = "https://analyticsdata.googleapis.com/v1beta"
GA4_ADMIN_URL = "https://analyticsadmin.googleapis.com/v1beta"
GSC_BASE_URL = "https://www.googleapis.com/webmasters/v3"


async def _refresh_access_token(refresh_token: str) -> tuple[Optional[str], int]:
    """Exchange refresh_token for access_token. Returns (access_token, expires_in)."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        logger.warning("Google OAuth not configured (GOOGLE_CLIENT_ID/SECRET missing)")
        return None, 0
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
        logger.warning("Token refresh failed: status=%s body=%s", resp.status_code, resp.text[:300])
        return None, 0
    data = resp.json()
    return data.get("access_token"), data.get("expires_in", 3600)


async def list_ga4_properties(access_token: str) -> list[dict[str, str]]:
    """List all GA4 properties accessible via the token. Returns [{ property_id, display_name }]."""
    url = f"{GA4_ADMIN_URL}/accountSummaries"
    headers = {"Authorization": f"Bearer {access_token}"}
    result: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers=headers)
    if r.status_code != 200:
        err_body = r.text[:500] if r.text else ""
        logger.warning("GA4 properties API error: status=%s body=%s", r.status_code, err_body)
        if r.status_code == 403 and "has not been used in project" in err_body:
            raise RuntimeError("Google Analytics Admin API is niet ingeschakeld in je Google Cloud project. Schakel deze in via de Google Cloud Console.")
        raise PermissionError(f"GA4 API error: {r.status_code}")
    data = r.json()
    for acc in data.get("accountSummaries", []):
        account_display = acc.get("displayName", "") or ""
        for prop in acc.get("propertySummaries", []):
            name = prop.get("property", "")
            if name.startswith("properties/"):
                pid = name.replace("properties/", "")
                raw_display = prop.get("displayName") or ""
                # Naam + ID: use property displayName; if missing or same as ID use account name or fallback
                if raw_display and raw_display != pid:
                    display = raw_display
                elif account_display:
                    display = account_display
                else:
                    display = f"Property {pid}"
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
        if r.status_code == 403 and "has not been used in project" in err_body:
            raise RuntimeError("Google Search Console API is niet ingeschakeld in je Google Cloud project. Schakel deze in via de Google Cloud Console.")
        raise PermissionError(f"GSC API error: {r.status_code}")
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


_CUSTOMER_CLIENT_QUERY = """
    SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, customer_client.level
    FROM customer_client
    WHERE customer_client.level <= 1
"""


async def list_google_ads_accounts(refresh_token: str) -> Tuple[list[dict[str, str]], Optional[str]]:
    """List all Google Ads accounts accessible via the token, including MCC sub-accounts.
    Returns (accounts, login_customer_id). login_customer_id is the MCC used (env or auto-detected) for use when fetching campaign data."""
    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        raise RuntimeError("google-ads package not installed")
    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN]):
        raise RuntimeError("GOOGLE_ADS_DEVELOPER_TOKEN not configured")
    base_config = {
        "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }
    mcc_config = {**base_config}
    login_customer_id: Optional[str] = (GOOGLE_ADS_LOGIN_CUSTOMER_ID or "").strip() or None
    if login_customer_id:
        login_customer_id = login_customer_id.replace("-", "")
        mcc_config["login_customer_id"] = login_customer_id
    try:
        client = GoogleAdsClient.load_from_dict(base_config)
        customer_service = client.get_service("CustomerService")
        response = customer_service.list_accessible_customers()

        accessible_ids = [r.replace("customers/", "") for r in response.resource_names if r.startswith("customers/")]
        # Find all MCCs: each accessible_id that returns customer_client results is an MCC
        mcc_ids: list[str] = []
        if login_customer_id:
            mcc_ids = [login_customer_id]
        elif accessible_ids:
            for aid in accessible_ids:
                try:
                    test_config = {**base_config, "login_customer_id": aid}
                    test_client = GoogleAdsClient.load_from_dict(test_config)
                    ga = test_client.get_service("GoogleAdsService")
                    stream = ga.search_stream(customer_id=aid, query=_CUSTOMER_CLIENT_QUERY)
                    for batch in stream:
                        if batch.results:
                            mcc_ids.append(aid)
                            logger.info("Google Ads MCC found: %s", aid)
                            break
                except (GoogleAdsException, Exception):
                    continue
            if mcc_ids and not login_customer_id:
                login_customer_id = mcc_ids[0]

        seen: set[str] = set()
        result: list[dict[str, str]] = []

        for resource_name in response.resource_names:
            if not resource_name.startswith("customers/"):
                continue
            raw_id = resource_name.replace("customers/", "")
            descriptive_name = ""
            try:
                customer = customer_service.get_customer(resource_name=resource_name)
                raw_id = str(customer.id)
                descriptive_name = getattr(customer, "descriptive_name", None) or ""
            except (GoogleAdsException, Exception) as e:
                logger.debug("get_customer %s failed: %s", resource_name, e)
            cid = _format_customer_id(raw_id)
            if raw_id not in seen:
                seen.add(raw_id)
                result.append({
                    "id": cid,
                    "name": descriptive_name or cid,
                    "customer_id": raw_id,
                    "descriptive_name": descriptive_name or cid,
                    "login_customer_id": None,
                })

        # For each MCC, use a client with that MCC as login_customer_id to fetch its sub-accounts
        to_process: list[str] = list(mcc_ids)
        while to_process:
            mcc_id = to_process.pop(0)
            try:
                seed_config = {**base_config, "login_customer_id": mcc_id}
                seed_client = GoogleAdsClient.load_from_dict(seed_config)
                ga_service = seed_client.get_service("GoogleAdsService")
                stream = ga_service.search_stream(customer_id=mcc_id, query=_CUSTOMER_CLIENT_QUERY)
                for batch in stream:
                    for row in batch.results:
                        customer = row.customer_client
                        descriptive_name = getattr(customer, "descriptive_name", None) or ""
                        cid = _format_customer_id(str(customer.id))
                        raw_id = str(customer.id)
                        if raw_id in seen:
                            continue
                        seen.add(raw_id)
                        result.append({
                            "id": cid,
                            "name": descriptive_name or cid,
                            "customer_id": raw_id,
                            "descriptive_name": descriptive_name or cid,
                            "login_customer_id": mcc_id,
                        })
                        # Nested MCC: query its children with its own client
                        if getattr(customer, "manager", False) and getattr(customer, "level", 0) == 1:
                            to_process.append(raw_id)
            except (GoogleAdsException, Exception) as e:
                logger.debug("customer_client query for MCC %s failed: %s", mcc_id, e)

        # Top-level accounts: assign default MCC if we have one (for backward compat)
        if login_customer_id:
            for acc in result:
                if acc.get("login_customer_id") is None:
                    acc["login_customer_id"] = login_customer_id
        return (result, login_customer_id)
    except Exception as e:
        logger.warning("List Google Ads accounts failed: %s", e)
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
        "use_proto_plus": True,
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


async def get_valid_access_token(
    conn, user_id: str, client_slug: str, integration_type: str
) -> Optional[str]:
    """
    Haalt access_token op. Als verlopen: vernieuwt via refresh_token en slaat op.
    Returns None als token niet beschikbaar of refresh mislukt.
    Backward compatible: als expires_at ontbreekt in extra_config, refresh altijd.
    """
    row = await conn.fetchrow(
        """
        SELECT extra_config, api_key_encrypted
        FROM client_integrations
        WHERE user_id = $1 AND client_slug = $2 AND integration_type = $3
        """,
        user_id,
        client_slug,
        integration_type,
    )
    if not row:
        return None

    extra = row["extra_config"] or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except Exception:
            extra = {}
    extra = dict(extra or {})

    access_token = extra.get("access_token")
    refresh_token = extra.get("refresh_token") or row.get("api_key_encrypted")

    # Check of access_token nog geldig is (60s marge)
    expires_at = extra.get("expires_at")
    now_ts = int(datetime.utcnow().timestamp())
    if expires_at and now_ts < expires_at - 60:
        return access_token

    # Refresh nodig (of expires_at ontbreekt — backward compatible)
    if not refresh_token:
        logger.warning(
            "get_valid_access_token: no refresh_token for user_id=%s client_slug=%s integration_type=%s",
            user_id,
            client_slug,
            integration_type,
        )
        return None

    new_access_token, expires_in = await _refresh_access_token(refresh_token)
    if not new_access_token:
        logger.warning(
            "get_valid_access_token: refresh failed for user_id=%s client_slug=%s integration_type=%s",
            user_id,
            client_slug,
            integration_type,
        )
        return None

    new_expires_at = now_ts + expires_in
    extra["access_token"] = new_access_token
    extra["expires_at"] = new_expires_at
    extra["oauth_connected"] = True
    await conn.execute(
        """
        UPDATE client_integrations
        SET extra_config = $1::jsonb, updated_at = now()
        WHERE user_id = $2 AND client_slug = $3 AND integration_type = $4
        """,
        json.dumps(extra),
        user_id,
        client_slug,
        integration_type,
    )
    return new_access_token


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
                    sess = int(metrics[1].get("value", 0)) if len(metrics) > 1 else 0
                    conv = float(metrics[2].get("value", 0)) if len(metrics) > 2 else 0
                    result["traffic_by_channel"].append({
                        "channel": dims[0].get("value", "(not set)"),
                        "users": int(metrics[0].get("value", 0)) if len(metrics) > 0 else 0,
                        "sessions": sess,
                        "conversions": conv,
                        "conversion_rate": (conv / sess * 100) if sess else 0.0,
                    })

    return result


async def fetch_google_ads_via_gaql(
    refresh_token: str,
    customer_id: str,
    start_date: str,
    end_date: str,
    login_customer_id: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch Google Ads via GAQL. login_customer_id (MCC) from koppeling or env."""
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
        "use_proto_plus": True,
    }
    mcc_id = (login_customer_id or "").replace("-", "").strip() or GOOGLE_ADS_LOGIN_CUSTOMER_ID
    if mcc_id:
        config["login_customer_id"] = mcc_id
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
    *,
    slug: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch Search Console: clicks, impressions, CTR, position, top queries, top pages.
    site_url should come from client_integrations.extra_config for the client."""
    if slug is not None:
        logger.info("GSC site_url for %s: %s", slug, site_url)
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


async def get_client_seo_summary_for_agent(pool, user_id: str, client_slug: str) -> Optional[str]:
    """
    Build a short text summary of GSC data for a client, for injection into agent/Direct Chat context.
    Returns None if client not found or on error; otherwise a string like:
    "Client Asured (@asured). Google Search Console (laatste 30 dagen): top zoektermen: X (N clicks), ..."
    """
    if not pool or not user_id or not client_slug:
        return None
    try:
        async with pool.acquire() as conn:
            client = await conn.fetchrow(
                "SELECT slug, client_name FROM clients WHERE user_id = $1 AND slug = $2",
                user_id,
                client_slug,
            )
            if not client:
                return None
            client_name = client["client_name"] or client_slug

            integrations = await conn.fetch(
                """
                SELECT integration_type, api_key_encrypted, extra_config
                FROM client_integrations
                WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'google_search_console'
                """,
                user_id,
                client_slug,
            )
            configs = await conn.fetch(
                """
                SELECT platform, config FROM client_platform_configs
                WHERE user_id = $1 AND client_slug = $2 AND platform = 'gsc'
                """,
                user_id,
                client_slug,
            )
        int_by_type = {r["integration_type"]: r for r in integrations}
        config_by_platform = {r["platform"]: (r["config"] or {}) for r in configs}
        gsc_int = int_by_type.get("google_search_console")
        gsc_cfg = config_by_platform.get("gsc", {})
        site_url = None
        if gsc_int and gsc_int.get("extra_config"):
            extra = gsc_int["extra_config"]
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except Exception:
                    extra = {}
            if isinstance(extra, dict) and extra.get("site_url"):
                site_url = extra["site_url"]
        if not site_url and isinstance(gsc_cfg, dict) and gsc_cfg.get("site_url"):
            site_url = gsc_cfg["site_url"]

        if not gsc_int:
            return (
                f"Client {client_name} (@{client_slug}). Google Search Console is niet gekoppeld voor deze client. "
                "Zeg de gebruiker dat ze onder Clients → [client] → Integraties Google Search Console kunnen koppelen om zoektermdata te zien."
            )

        async with pool.acquire() as conn:
            access_token = await get_valid_access_token(conn, user_id, client_slug, "google_search_console")
        if not access_token:
            return (
                f"Client {client_name} (@{client_slug}). Google Search Console: token ontbreekt of verlopen. "
                "Raad de gebruiker aan om onder Integraties opnieuw te koppelen."
            )

        if not site_url:
            site_url = await _get_first_gsc_site(access_token)
        if not site_url:
            return (
                f"Client {client_name} (@{client_slug}). Google Search Console is gekoppeld maar geen site gekozen. "
                "Zeg de gebruiker dat ze onder Integraties een site moeten selecteren."
            )

        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        gsc_data = await fetch_gsc(access_token, site_url, start_str, end_str, slug=client_slug)

        parts = [f"Client {client_name} (@{client_slug}). Google Search Console (laatste 30 dagen):"]
        totals = gsc_data.get("totals") or {}
        parts.append(f"Totaal: {totals.get('clicks', 0)} clicks, {totals.get('impressions', 0)} impressies, positie ~{totals.get('position', 0):.1f}.")
        top = gsc_data.get("top_queries") or []
        if top:
            query_str = "; ".join(f'"{q.get("query", "")}" ({q.get("clicks", 0)} clicks)' for q in top[:10])
            parts.append(f"Top zoektermen: {query_str}.")
        else:
            parts.append("Geen top zoektermen beschikbaar.")
        return " ".join(parts)
    except Exception as e:
        logger.warning("get_client_seo_summary_for_agent failed: user_id=%s client_slug=%s %s", user_id, client_slug, e)
        return None
