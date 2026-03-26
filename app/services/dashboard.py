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
    PAGESPEED_API_KEY,
)

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GA4_RUN_REPORT_URL = "https://analyticsdata.googleapis.com/v1beta"
GA4_ADMIN_URL = "https://analyticsadmin.googleapis.com/v1beta"
GSC_BASE_URL = "https://www.googleapis.com/webmasters/v3"
PAGESPEED_BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


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
    WHERE customer_client.level <= 3
"""


def _list_google_ads_accounts_result(
    mcc_accounts: list[dict], login_customer_id: Optional[str]
) -> Tuple[list[dict], list[dict], Optional[str]]:
    """Return (mcc_accounts, flat_accounts, login_customer_id). Flat list = all children for backwards compat."""
    flat: list[dict] = []
    for mcc in mcc_accounts:
        for child in mcc.get("children", []):
            flat.append(dict(child))
    return (mcc_accounts, flat, login_customer_id)


async def list_google_ads_accounts(
    refresh_token: str,
) -> Tuple[list[dict], list[dict], Optional[str]]:
    """List Google Ads accounts grouped by MCC. Only non-manager (child) accounts are selectable.
    Returns (mcc_accounts, flat_accounts, login_customer_id)."""
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
    login_customer_id: Optional[str] = (GOOGLE_ADS_LOGIN_CUSTOMER_ID or "").strip() or None
    if login_customer_id:
        login_customer_id = login_customer_id.replace("-", "")
    try:
        client = GoogleAdsClient.load_from_dict(base_config)
        customer_service = client.get_service("CustomerService")
        response = customer_service.list_accessible_customers()
        logger.info("GA Ads accessible resource_names: %s", response.resource_names)

        accessible_ids = [r.replace("customers/", "") for r in response.resource_names if r.startswith("customers/")]
        mcc_ids: list[str] = []
        logger.info("GA Ads login_customer_id=%r (from env GOOGLE_ADS_LOGIN_CUSTOMER_ID=%r)", login_customer_id, GOOGLE_ADS_LOGIN_CUSTOMER_ID)
        if login_customer_id:
            mcc_ids = [login_customer_id]
        elif accessible_ids:
            for aid in accessible_ids:
                logger.info("GA Ads testing customer as MCC: %s", aid)
                child_count = 0
                try:
                    test_config = {**base_config, "login_customer_id": aid}
                    test_client = GoogleAdsClient.load_from_dict(test_config)
                    ga = test_client.get_service("GoogleAdsService")
                    logger.info("GA Ads testing MCC candidate: %s", aid)
                    stream = ga.search_stream(customer_id=aid, query=_CUSTOMER_CLIENT_QUERY)
                    for batch in stream:
                        for row in batch.results:
                            level = getattr(row.customer_client, "level", 0)
                            if level > 0:
                                child_count += 1
                    logger.info(
                        "GA Ads customer %s has %s children, treating as MCC: %s",
                        aid, child_count, child_count > 0,
                    )
                    if child_count > 0:
                        mcc_ids.append(aid)
                except (GoogleAdsException, Exception) as e:
                    logger.warning("GA Ads MCC test failed for %s: %s", aid, str(e))
                    continue
            if mcc_ids and not login_customer_id:
                login_customer_id = mcc_ids[0]

        # mcc_id (raw) -> { mcc_name, children[] }; only manager=false in children
        mcc_data: dict[str, dict] = {}
        to_process: list[str] = list(mcc_ids)
        seen_children: set[str] = set()
        logger.info("GA Ads MCC ids to process: %s", list(to_process))

        while to_process:
            mcc_id = to_process.pop(0)
            if mcc_id not in mcc_data:
                mcc_data[mcc_id] = {"mcc_name": _format_customer_id(mcc_id), "children": []}
            try:
                seed_config = {**base_config, "login_customer_id": mcc_id}
                seed_client = GoogleAdsClient.load_from_dict(seed_config)
                ga_service = seed_client.get_service("GoogleAdsService")
                stream = ga_service.search_stream(customer_id=mcc_id, query=_CUSTOMER_CLIENT_QUERY)
                for batch in stream:
                    for row in batch.results:
                        customer = row.customer_client
                        raw_id = str(customer.id)
                        is_manager = getattr(customer, "manager", False)
                        descriptive_name = getattr(customer, "descriptive_name", None) or ""
                        cid = _format_customer_id(raw_id)
                        logger.info(
                            "GA Ads row: id=%s manager=%s level=%s name=%s",
                            getattr(customer, "id", raw_id),
                            getattr(customer, "manager", None),
                            getattr(customer, "level", None),
                            getattr(customer, "descriptive_name", "") or "",
                        )

                        if raw_id == mcc_id:
                            mcc_data[mcc_id]["mcc_name"] = descriptive_name or cid
                        if is_manager:
                            if raw_id != mcc_id:
                                to_process.append(raw_id)
                                if raw_id not in mcc_data:
                                    mcc_data[raw_id] = {"mcc_name": descriptive_name or cid, "children": []}
                            continue
                        # Only non-manager (child) accounts are selectable
                        if raw_id in seen_children:
                            continue
                        seen_children.add(raw_id)
                        mcc_data[mcc_id]["children"].append({
                            "customer_id": raw_id,
                            "id": cid,
                            "descriptive_name": descriptive_name or cid,
                            "name": descriptive_name or cid,
                            "login_customer_id": mcc_id,
                        })
            except (GoogleAdsException, Exception) as e:
                logger.debug("customer_client query for MCC %s failed: %s", mcc_id, e)

        logger.info(
            "GA Ads result: mccs=%s total_children=%s",
            len(mcc_data),
            sum(len(v["children"]) for v in mcc_data.values()),
        )
        mcc_accounts = [
            {
                "mcc_id": _format_customer_id(mid),
                "mcc_name": data["mcc_name"],
                "children": data["children"],
            }
            for mid, data in mcc_data.items()
        ]
        return _list_google_ads_accounts_result(mcc_accounts, login_customer_id)
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

    Resolutie: platform-owned credentials eerst, daarna user-owned (zie credential_resolver).
    """
    from app.services.credential_resolver import resolve_integration_row

    row = await resolve_integration_row(
        conn,
        client_slug=client_slug or "",
        integration_type=integration_type,
        user_id=user_id or None,
    )
    if not row:
        return None

    extra = row["extra_config"] or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra) if extra.strip() else {}
        except Exception:
            extra = {}
    if not isinstance(extra, dict):
        extra = {}

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
    integration_id = row.get("integration_id")
    if integration_id:
        await conn.execute(
            """
            UPDATE client_integrations
            SET extra_config = $1::jsonb, updated_at = now()
            WHERE integration_id = $2
            """,
            json.dumps(extra),
            integration_id,
        )
    else:
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
        data = r.json() if r.content else {}
        data = data if isinstance(data, dict) else {}
        rows = data.get("rows", []) if isinstance(data.get("rows"), list) else []
        if rows:
            row = rows[0] if isinstance(rows[0], dict) else {}
            metrics = row.get("metricValues", []) if isinstance(row.get("metricValues"), list) else []
            def _mval(i: int, default: float = 0):
                if i >= len(metrics): return default
                m = metrics[i]
                return float(m.get("value", default)) if isinstance(m, dict) else default
            result["kpis"] = {
                "users": int(_mval(0)),
                "sessions": int(_mval(1)),
                "conversions": _mval(2),
                "conversion_value": _mval(3),
                "engagement_rate": _mval(4),
            }
            if result["kpis"]["sessions"] > 0:
                result["kpis"]["conversion_rate"] = (
                    result["kpis"]["conversions"] / result["kpis"]["sessions"] * 100
                )
            else:
                result["kpis"]["conversion_rate"] = 0.0

        # Time series (GA4 API returns date dimension as YYYYMMDD; normalize to YYYY-MM-DD for frontend merge with Ads)
        r = await client.post(url, headers=headers, json=timeseries_body)
        if r.status_code == 200:
            data = r.json() if r.content else {}
            data = data if isinstance(data, dict) else {}
            for row in (data.get("rows") or []):
                if not isinstance(row, dict):
                    continue
                dims = row.get("dimensionValues", []) if isinstance(row.get("dimensionValues"), list) else []
                metrics = row.get("metricValues", []) if isinstance(row.get("metricValues"), list) else []
                if dims and metrics and isinstance(dims[0], dict):
                    raw_date = dims[0].get("value", "")
                    if len(raw_date) == 8 and raw_date.isdigit():
                        date_val = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                    else:
                        date_val = raw_date
                    def _mv(i: int):
                        if i >= len(metrics) or not isinstance(metrics[i], dict):
                            return 0
                        return float(metrics[i].get("value", 0)) or 0
                    result["timeseries"].append({
                        "date": date_val,
                        "users": int(_mv(0)),
                        "sessions": int(_mv(1)),
                        "conversions": _mv(2),
                        "conversion_value": _mv(3),
                    })

        # Traffic by channel
        r = await client.post(url, headers=headers, json=channel_body)
        if r.status_code == 200:
            data = r.json() if r.content else {}
            data = data if isinstance(data, dict) else {}
            for row in (data.get("rows") or []):
                if not isinstance(row, dict):
                    continue
                dims = row.get("dimensionValues", []) if isinstance(row.get("dimensionValues"), list) else []
                metrics = row.get("metricValues", []) if isinstance(row.get("metricValues"), list) else []
                if not dims or not metrics or not isinstance(dims[0], dict):
                    continue
                def _mv2(i: int):
                    if i >= len(metrics) or not isinstance(metrics[i], dict):
                        return 0
                    return float(metrics[i].get("value", 0)) or 0
                sess = int(_mv2(1))
                conv = _mv2(2)
                result["traffic_by_channel"].append({
                    "channel": dims[0].get("value", "(not set)"),
                    "users": int(_mv2(0)),
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


GSC_UI_LIMIT = 10
GSC_STORAGE_ROW_LIMIT = 500


async def fetch_gsc(
    access_token: str,
    site_url: str,
    start_date: str,
    end_date: str,
    *,
    slug: Optional[str] = None,
    pool: Any = None,
) -> dict[str, Any]:
    """Fetch Search Console: clicks, impressions, CTR, position, top queries, top pages.
    Fetches up to GSC_STORAGE_ROW_LIMIT for queries/pages; stores full snapshot when pool+slug given;
    returns top GSC_UI_LIMIT for UI. site_url from client_integrations.extra_config."""
    if slug is not None:
        logger.info("GSC site_url for %s: %s", slug, site_url)
    import urllib.parse
    site_encoded = urllib.parse.quote(site_url, safe="")
    url = f"{GSC_BASE_URL}/sites/{site_encoded}/searchAnalytics/query"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    totals = {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}
    full_queries: list[dict[str, Any]] = []
    full_pages: list[dict[str, Any]] = []
    timeseries: list[dict[str, Any]] = []

    body = {"startDate": start_date, "endDate": end_date}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=body)
        if r.status_code != 200:
            logger.warning("GSC totals failed: %s %s", r.status_code, r.text)
            return {
                "totals": totals,
                "top_queries": [],
                "top_pages": [],
                "timeseries": [],
            }
        data = r.json()
        rows = data.get("rows", [])
        if rows and isinstance(rows[0], dict):
            row = rows[0]
            totals = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0),
                "position": row.get("position", 0),
            }

        body_query = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "rowLimit": GSC_STORAGE_ROW_LIMIT,
        }
        r = await client.post(url, headers=headers, json=body_query)
        if r.status_code == 200:
            data = r.json()
            for row in data.get("rows", []):
                keys = row.get("keys", [])
                full_queries.append({
                    "query": keys[0] if keys else "(not set)",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0),
                    "position": row.get("position", 0),
                })

        body_page = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page"],
            "rowLimit": GSC_STORAGE_ROW_LIMIT,
        }
        r = await client.post(url, headers=headers, json=body_page)
        if r.status_code == 200:
            data = r.json()
            for row in data.get("rows", []):
                keys = row.get("keys", [])
                full_pages.append({
                    "page": keys[0] if keys else "(not set)",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0),
                    "position": row.get("position", 0),
                })

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
                timeseries.append({
                    "date": keys[0] if keys else "",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                })

    if pool and slug:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO gsc_snapshots (client_id, date_range_start, date_range_end, queries, pages, totals)
                    VALUES ($1, $2::date, $3::date, $4::jsonb, $5::jsonb, $6::jsonb)
                    """,
                    slug,
                    start_date,
                    end_date,
                    json.dumps(full_queries),
                    json.dumps(full_pages),
                    json.dumps(totals),
                )
                await conn.execute(
                    """
                    WITH kept AS (
                        SELECT id FROM gsc_snapshots
                        WHERE client_id = $1
                        ORDER BY fetched_at DESC
                        LIMIT 4
                    )
                    DELETE FROM gsc_snapshots
                    WHERE client_id = $1 AND id NOT IN (SELECT id FROM kept)
                    """,
                    slug,
                )
        except Exception as e:
            logger.warning("GSC snapshot save failed for client %s: %s", slug, e)

    return {
        "totals": totals,
        "top_queries": full_queries[:GSC_UI_LIMIT],
        "top_pages": full_pages[:GSC_UI_LIMIT],
        "timeseries": timeseries,
    }


async def fetch_gsc_top_pages(
    access_token: str,
    site_url: str,
    start_date: str,
    end_date: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Fetch top pages from GSC for a date range. Used by DataAgent.
    Returns list of dicts: page, clicks, impressions, ctr, position.
    """
    import urllib.parse
    site_encoded = urllib.parse.quote(site_url, safe="")
    url = f"{GSC_BASE_URL}/sites/{site_encoded}/searchAnalytics/query"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["page"],
        "rowLimit": min(limit, 25000),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=body)
        if r.status_code != 200:
            logger.warning("GSC top_pages failed: %s %s", r.status_code, r.text[:300])
            return []
        data = r.json()
        pages: list[dict[str, Any]] = []
        for row in data.get("rows", []):
            keys = row.get("keys", [])
            pages.append({
                "page": keys[0] if keys else "(not set)",
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0),
                "position": row.get("position", 0),
            })
        return pages


async def fetch_lighthouse(url: str) -> dict[str, Any]:
    """Fetch Lighthouse categories for mobile and desktop via PageSpeed Insights API."""
    result: dict[str, Any] = {
        "mobile": {},
        "desktop": {},
    }
    if not url:
        return result
    if not PAGESPEED_API_KEY:
        return {"error": "PAGESPEED_API_KEY not configured"}

    async def _run(strategy: str) -> dict[str, Any]:
        params = {
            "url": url,
            "strategy": strategy,
            "category": ["performance", "accessibility", "best-practices", "seo"],
            "key": PAGESPEED_API_KEY,
        }
        async with httpx.AsyncClient(timeout=40.0) as client:
            r = await client.get(PAGESPEED_BASE_URL, params=params)
        if r.status_code != 200:
            logger.warning("Lighthouse API failed: strategy=%s status=%s body=%s", strategy, r.status_code, r.text[:300])
            return {"error": f"Lighthouse API error: {r.status_code}"}

        data = r.json() if r.content else {}
        data = data if isinstance(data, dict) else {}
        lhr = data.get("lighthouseResult") if isinstance(data.get("lighthouseResult"), dict) else {}
        categories = lhr.get("categories") if isinstance(lhr.get("categories"), dict) else {}

        def _score(cat: str) -> int:
            raw = categories.get(cat, {}).get("score") if isinstance(categories.get(cat), dict) else None
            return int(round(float(raw or 0) * 100))

        return {
            "performance": _score("performance"),
            "accessibility": _score("accessibility"),
            "best_practices": _score("best-practices"),
            "seo": _score("seo"),
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }

    result["mobile"] = await _run("mobile")
    result["desktop"] = await _run("desktop")
    return result


async def fetch_meta_ads(
    access_token: str,
    ad_account_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """
    Fetch Facebook Ads performance via Graph API Insights.
    Returns spend, clicks, impressions, conversions per campaign.
    """
    raw_id = (ad_account_id or "").strip()
    if not raw_id:
        return {
            "error": "no_ad_account_id",
            "campaigns": [],
            "message": "Geen Meta ad account ID geconfigureerd.",
        }
    # Graph API expects act_<numeric_id>
    account_path = raw_id if raw_id.startswith("act_") else f"act_{raw_id}"

    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=days)).isoformat()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"https://graph.facebook.com/v19.0/{account_path}/insights",
            params={
                "fields": "campaign_name,impressions,clicks,spend,actions,ctr,cpm,reach",
                "time_range": json.dumps({"since": date_from, "until": date_to}),
                "level": "campaign",
                "access_token": access_token,
            },
        )
    if resp.status_code != 200:
        err_msg: Optional[str] = None
        try:
            j = resp.json()
            fb_err = j.get("error")
            if isinstance(fb_err, dict):
                err_msg = fb_err.get("message") or str(fb_err.get("type") or "")
            elif isinstance(fb_err, str):
                err_msg = fb_err
        except Exception:
            pass
        if not err_msg:
            err_msg = (resp.text or "")[:500]
        logger.error("Meta Ads API error: %s %s", resp.status_code, err_msg)
        return {
            "error": "meta_api_error",
            "campaigns": [],
            "message": err_msg or f"HTTP {resp.status_code}",
        }
    data = resp.json().get("data", [])
    campaigns = []
    for c in data:
        conversions = 0
        for action in c.get("actions") or []:
            if action.get("action_type") in ("purchase", "lead", "complete_registration"):
                conversions += int(action.get("value", 0))
        campaigns.append({
            "name": c.get("campaign_name"),
            "impressions": int(c.get("impressions", 0)),
            "clicks": int(c.get("clicks", 0)),
            "spend": float(c.get("spend", 0)),
            "conversions": conversions,
            "ctr": float(c.get("ctr", 0)),
            "cpm": float(c.get("cpm", 0)),
            "reach": int(c.get("reach", 0)),
        })
    total_spend = sum(c["spend"] for c in campaigns)
    total_clicks = sum(c["clicks"] for c in campaigns)
    total_conversions = sum(c["conversions"] for c in campaigns)
    return {
        "period_days": days,
        "total_spend": round(total_spend, 2),
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "campaigns": campaigns,
    }


async def fetch_instagram_insights(
    page_access_token: str,
    instagram_business_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """Fetch Instagram Business Insights: reach, impressions, profile_views, follower_count."""
    since_ts = int((datetime.utcnow() - timedelta(days=days)).timestamp())
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"https://graph.facebook.com/v19.0/{instagram_business_id}/insights",
            params={
                "metric": "reach,impressions,profile_views,follower_count",
                "period": "day",
                "since": since_ts,
                "access_token": page_access_token,
            },
        )
    if resp.status_code != 200:
        logger.warning("Instagram Insights API error: %s %s", resp.status_code, resp.text[:200])
        return {"error": "instagram_api_error"}
    metrics = {}
    for item in resp.json().get("data", []):
        name = item.get("name")
        values = item.get("values", [])
        total = sum(v.get("value", 0) for v in values)
        metrics[name] = total
    return {
        "period_days": days,
        "reach": metrics.get("reach", 0),
        "impressions": metrics.get("impressions", 0),
        "profile_views": metrics.get("profile_views", 0),
        "follower_count": metrics.get("follower_count", 0),
    }


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

            from app.services.credential_resolver import resolve_integration_row

            gsc_row = await resolve_integration_row(
                conn,
                client_slug=client_slug,
                integration_type="google_search_console",
                user_id=user_id,
            )
            integrations = [gsc_row] if gsc_row else []
            configs = await conn.fetch(
                """
                SELECT platform, config FROM client_platform_configs
                WHERE user_id = $1 AND client_slug = $2 AND platform = 'gsc'
                """,
                user_id,
                client_slug,
            )
        int_by_type = {r["integration_type"]: r for r in integrations if r}
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
        gsc_data = await fetch_gsc(
            access_token, site_url, start_str, end_str, slug=client_slug, pool=pool
        )

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
