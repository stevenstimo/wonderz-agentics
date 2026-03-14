"""Clients API — client management and platform configs.

Uses clients.slug as identifier. client_platform_configs stores platform-specific IDs per client.
"""

import json
import logging
import os
import re
import secrets
import tempfile
from datetime import date, timedelta
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user
from app.services.client_crawler import ClientCrawler, get_sitemap_structure
from app.services.client_feed_processor import ClientFeedProcessor
from app.services.client_file_processor import ClientFileProcessor
from app.services.client_text_processor import ClientTextProcessor
from app.services.dashboard import (
    _get_first_ga4_property,
    _get_first_google_ads_customer,
    _get_first_gsc_site,
    _get_refresh_token,
    fetch_ga4,
    fetch_gsc,
    fetch_google_ads_via_gaql,
    fetch_instagram_insights,
    fetch_meta_ads,
    get_valid_access_token,
    list_ga4_properties,
    list_google_ads_accounts,
    list_gsc_sites,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _unwrap_extra(raw) -> dict:
    """Unwrap potentially double/triple-encoded JSONB extra_config to a dict."""
    for _ in range(3):
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return {}
        else:
            break
    return raw if isinstance(raw, dict) else {}


def _slug_from_name(name: str) -> str:
    """Generate slug from client name: lowercase, spaces to underscores."""
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "client"


class ClientCreateBody(BaseModel):
    client_name: str = Field(..., min_length=1)


class PlatformConfigBody(BaseModel):
    platform: str = Field(..., min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class IntegrationConfigBody(BaseModel):
    """Config for Google/Meta: property_id (ga4), site_url (gsc), customer_id + login_customer_id (google_ads), ad_account_id (meta_ads)."""
    property_id: Optional[str] = None
    site_url: Optional[str] = None
    customer_id: Optional[str] = None
    login_customer_id: Optional[str] = None
    ad_account_id: Optional[str] = None


class DatasourceCreateBody(BaseModel):
    """Create a client knowledge datasource."""
    name: str = Field(..., min_length=1)
    source_type: str = Field(..., pattern="^(website_crawl|website_sitemap|text|file|product_feed)$")
    domain: Optional[str] = None
    sitemap_url: Optional[str] = None
    raw_text: Optional[str] = None
    feed_url: Optional[str] = None
    feed_splitting_tag: Optional[str] = None
    feed_identifier_tag: Optional[str] = None


# --- Endpoints ---


@router.get("")
async def list_clients(current_user: TokenPayload = Depends(get_current_user)):
    """List all clients for the current user."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT client_id, slug, client_name, description, is_active, created_at
            FROM clients
            WHERE user_id = $1
            ORDER BY client_name
            """,
            current_user.user_id,
        )
    return [
        {
            "client_id": r["client_id"],
            "slug": r["slug"],
            "client_name": r["client_name"],
            "description": r["description"],
            "is_active": r["is_active"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.post("")
async def create_client(
    body: ClientCreateBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Create a new client."""
    slug = _slug_from_name(body.client_name)
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid client name")
    client_id = f"client:{current_user.user_id}:{slug}"
    pool = await get_db()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO clients (client_id, user_id, client_name, slug, is_active)
                VALUES ($1, $2, $3, $4, true)
                """,
                client_id,
                current_user.user_id,
                body.client_name.strip(),
                slug,
            )
        except Exception as e:
            if "clients_user_id_slug_key" in str(e) or "unique" in str(e).lower():
                raise HTTPException(status_code=409, detail="Client with this slug already exists")
            raise
    return {"status": "ok", "slug": slug, "client_id": client_id}


@router.get("/{slug}/google/ga4-properties")
async def get_ga4_properties(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List GA4 properties accessible via the client's OAuth tokens."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT slug FROM clients WHERE user_id = $1 AND slug = $2",
            current_user.user_id,
            slug,
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        access_token = await get_valid_access_token(
            conn, current_user.user_id, slug, "ga4"
        )
    if not access_token:
        raise HTTPException(status_code=401, detail="token_expired")
    try:
        props = await list_ga4_properties(access_token)
    except Exception as e:
        err_str = str(e)
        if "403" in err_str or "has not been used" in err_str or "API not enabled" in err_str:
            raise HTTPException(status_code=403, detail="google_api_not_enabled")
        elif "401" in err_str or "invalid_grant" in err_str or "Token has been expired" in err_str:
            raise HTTPException(status_code=401, detail="token_expired")
        raise HTTPException(status_code=500, detail=str(e))
    return props


@router.get("/{slug}/google/ads-accounts")
async def get_ads_accounts(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List Google Ads accounts accessible via the client's OAuth tokens."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT slug FROM clients WHERE user_id = $1 AND slug = $2",
            current_user.user_id,
            slug,
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        row = await conn.fetchrow(
            """
            SELECT api_key_encrypted, extra_config
            FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'google_ads'
            """,
            current_user.user_id,
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Google Ads not connected for this client")
    extra = _unwrap_extra(row["extra_config"])
    refresh = _get_refresh_token(row["api_key_encrypted"], extra)
    if not refresh:
        raise HTTPException(status_code=401, detail="token_expired")
    try:
        mcc_accounts, accounts, login_customer_id = await list_google_ads_accounts(refresh)
    except Exception as e:
        err_str = str(e)
        if "403" in err_str or "has not been used" in err_str or "API not enabled" in err_str:
            raise HTTPException(status_code=403, detail="google_api_not_enabled")
        elif "401" in err_str or "invalid_grant" in err_str or "Token has been expired" in err_str:
            raise HTTPException(status_code=401, detail="token_expired")
        raise HTTPException(status_code=500, detail=str(e))
    num_mccs = len(mcc_accounts)
    num_children = sum(len(mcc.get("children", [])) for mcc in mcc_accounts)
    logger.info(
        "Google Ads ads-accounts response: slug=%s, mccs=%s, children=%s",
        slug, num_mccs, num_children,
    )
    return {
        "mcc_accounts": mcc_accounts,
        "accounts": accounts,
        "login_customer_id": login_customer_id or None,
    }


@router.get("/{slug}/google/gsc-sites")
async def get_gsc_sites(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List GSC sites accessible via the client's OAuth tokens."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT slug FROM clients WHERE user_id = $1 AND slug = $2",
            current_user.user_id,
            slug,
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        access_token = await get_valid_access_token(
            conn, current_user.user_id, slug, "google_search_console"
        )
    if not access_token:
        raise HTTPException(status_code=401, detail="token_expired")
    try:
        sites = await list_gsc_sites(access_token)
    except Exception as e:
        err_str = str(e)
        if "403" in err_str or "has not been used" in err_str or "API not enabled" in err_str:
            raise HTTPException(status_code=403, detail="google_api_not_enabled")
        elif "401" in err_str or "invalid_grant" in err_str or "Token has been expired" in err_str:
            raise HTTPException(status_code=401, detail="token_expired")
        raise HTTPException(status_code=500, detail=str(e))
    return sites


@router.get("/{slug}/meta/auth-url")
async def get_meta_auth_url(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Generate Meta OAuth URL for this client."""
    app_id = os.getenv("META_APP_ID")
    redirect_uri = os.getenv("META_REDIRECT_URI")
    if not app_id or not redirect_uri:
        raise HTTPException(status_code=503, detail="Meta app not configured")
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT slug FROM clients WHERE user_id = $1 AND slug = $2",
            current_user.user_id,
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    state = f"{slug}:{secrets.token_urlsafe(16)}"
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": ",".join([
            "ads_read",
            "pages_read_engagement",
            "pages_show_list",
        ]),
        "response_type": "code",
        "state": state,
    }
    auth_url = f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"
    return {"auth_url": auth_url, "state": state}


@router.get("/{slug}/meta/ad-accounts")
async def get_meta_ad_accounts(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List Meta Ad Accounts accessible via the client's token."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT extra_config FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'meta_ads'
            """,
            current_user.user_id,
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Meta not connected for this client")
    cfg = row["extra_config"]
    if isinstance(cfg, str):
        cfg = json.loads(cfg) if cfg else {}
    if not isinstance(cfg, dict):
        cfg = {}
    access_token = cfg.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="token_expired")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://graph.facebook.com/v19.0/me/adaccounts",
            params={
                "fields": "id,name,account_id,currency,account_status",
                "access_token": access_token,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="token_expired")
    data = resp.json().get("data", [])
    return {
        "accounts": [
            {"id": acc["id"], "name": acc.get("name", acc["id"]), "account_id": acc.get("account_id")}
            for acc in data
        ]
    }


@router.get("/{slug}/meta/pages")
async def get_meta_pages(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List Facebook Pages for the connected Meta account."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT extra_config FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'meta_ads'
            """,
            current_user.user_id,
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Meta not connected")
    cfg = row["extra_config"]
    if isinstance(cfg, str):
        cfg = json.loads(cfg) if cfg else {}
    if not isinstance(cfg, dict):
        cfg = {}
    access_token = cfg.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="token_expired")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={
                "fields": "id,name,access_token,instagram_business_account",
                "access_token": access_token,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="token_expired")
    data = resp.json().get("data", [])
    pages = []
    for p in data:
        ig = p.get("instagram_business_account") or {}
        pages.append({
            "id": p["id"],
            "name": p.get("name"),
            "has_instagram": bool(ig),
            "instagram_id": ig.get("id") if isinstance(ig, dict) else None,
        })
    return {"pages": pages}


@router.get("/{slug}/dashboard")
async def get_client_dashboard(
    slug: str,
    start: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    channel: Optional[str] = Query(None, description="GA4 channel filter"),
    device: Optional[str] = Query(None, description="GA4 device filter"),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get marketing dashboard data for a client: GA4, Google Ads, GSC.
    Returns null with not_connected for integrations that are not linked."""
    pool = await get_db()
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    if start:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            pass
    if end:
        try:
            end_date = date.fromisoformat(end)
        except ValueError:
            pass
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()
    logger.info("Dashboard date range: slug=%s start=%s end=%s", slug, start_str, end_str)

    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT slug, client_name FROM clients WHERE user_id = $1 AND slug = $2",
            current_user.user_id,
            slug,
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        integrations = await conn.fetch(
            """
            SELECT integration_type, api_key_encrypted, extra_config
            FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type IN ('ga4', 'google_ads', 'google_search_console', 'meta_ads')
            """,
            current_user.user_id,
            slug,
        )
        configs = await conn.fetch(
            """
            SELECT platform, config
            FROM client_platform_configs
            WHERE user_id = $1 AND client_slug = $2 AND platform IN ('ga4', 'google_ads', 'gsc')
            """,
            current_user.user_id,
            slug,
        )

    int_by_type = {r["integration_type"]: r for r in integrations}
    # Normalize config to dict (asyncpg usually returns jsonb as dict; defensive for string/None)
    config_by_platform = {}
    for r in configs:
        c = r.get("config")
        config_by_platform[r["platform"]] = c if isinstance(c, dict) else {}

    result: dict[str, Any] = {
        "overview": None,
        "ga4": None,
        "google_ads": None,
        "gsc": None,
        "meta": None,
    }

    # --- GA4 ---
    ga4_int = int_by_type.get("ga4")
    ga4_cfg = config_by_platform.get("ga4", {})
    # Primary: client_integrations.extra_config; fallback: client_platform_configs.config
    ga4_extra = _unwrap_extra(ga4_int.get("extra_config") if ga4_int else None)
    property_id = ga4_extra.get("property_id") or (ga4_cfg.get("property_id") if isinstance(ga4_cfg, dict) else None)
    ga4_used_fallback = False

    if not ga4_int:
        result["ga4"] = {"not_connected": True}
    else:
        async with pool.acquire() as conn:
            access_token = await get_valid_access_token(
                conn, current_user.user_id, slug, "ga4"
            )
        if not access_token:
            result["ga4"] = {"not_connected": True, "error": "Token refresh failed"}
        else:
            if not property_id:
                property_id = await _get_first_ga4_property(access_token)
                if property_id:
                    ga4_used_fallback = True
                    logger.info("Dashboard ga4: no property_id saved for %s, using first property %s", slug, property_id)
            if not property_id:
                result["ga4"] = {"not_connected": True, "error": "No GA4 property found. Kies een property onder Integraties."}
            else:
                try:
                    ga4_data = await fetch_ga4(
                        access_token, property_id, start_str, end_str, channel, device
                    )
                    result["ga4"] = ga4_data
                    if ga4_used_fallback:
                        result["ga4"]["_used_first_property"] = True
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                INSERT INTO client_platform_configs
                                    (config_id, user_id, client_slug, client_name, platform, config, is_active)
                                VALUES ($1, $2, $3, $4, 'ga4', $5::jsonb, true)
                                ON CONFLICT (user_id, client_slug, platform)
                                DO UPDATE SET config = client_platform_configs.config || $5::jsonb, is_active = true
                                """,
                                f"cfg:{slug}:ga4",
                                current_user.user_id,
                                slug,
                                client["client_name"],
                                json.dumps({"property_id": property_id}),
                            )
                except Exception as e:
                    logger.exception("GA4 fetch failed")
                    result["ga4"] = {"not_connected": False, "error": str(e)}

    # --- Google Ads ---
    ads_int = int_by_type.get("google_ads")
    ads_cfg = config_by_platform.get("google_ads", {})
    # Prefer customer_id from extra_config (google_ads_customer_id or customer_id), then platform config
    extra_config = _unwrap_extra(ads_int.get("extra_config") if ads_int else None)
    customer_id = (
        extra_config.get("google_ads_customer_id")
        or extra_config.get("customer_id")
        or (ads_cfg.get("customer_id") if isinstance(ads_cfg, dict) else None)
    )
    ads_used_fallback = False

    if not ads_int:
        result["google_ads"] = {"not_connected": True}
    else:
        extra = _unwrap_extra(ads_int.get("extra_config"))
        refresh = _get_refresh_token(ads_int["api_key_encrypted"], extra)
        if not refresh:
            result["google_ads"] = {"not_connected": True}
        elif not customer_id:
            # Fallback: use first accessible account (e.g. when user never picked one in dropdown)
            customer_id = await _get_first_google_ads_customer(refresh)
            if customer_id:
                ads_used_fallback = True
                logger.info("Dashboard google_ads: no customer_id saved for %s, using first account %s", slug, customer_id)
            else:
                result["google_ads"] = {
                    "campaigns": [],
                    "timeseries": [],
                    "total_spend": 0,
                    "total_clicks": 0,
                    "total_impressions": 0,
                }
        if customer_id:
            login_cid = extra_config.get("login_customer_id") if isinstance(extra_config, dict) else None
            try:
                ads_data = await fetch_google_ads_via_gaql(
                    refresh, customer_id, start_str, end_str, login_customer_id=login_cid
                )
                if ads_data.get("not_implemented") or ads_data.get("not_configured"):
                    result["google_ads"] = {"not_connected": True, "error": ads_data.get("error", "Google Ads not configured")}
                elif ads_data.get("error"):
                    result["google_ads"] = {"not_connected": False, "error": ads_data["error"]}
                else:
                    result["google_ads"] = ads_data
                    if ads_used_fallback:
                        result["google_ads"]["_used_first_account"] = True
                        fallback_extra = {"customer_id": customer_id}
                        if not (extra_config.get("login_customer_id") if isinstance(extra_config, dict) else None):
                            try:
                                _, _, mcc_id = await list_google_ads_accounts(refresh)
                                if mcc_id:
                                    fallback_extra["login_customer_id"] = mcc_id
                            except Exception:
                                pass
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE client_integrations
                                SET extra_config = extra_config || $1::jsonb, updated_at = now()
                                WHERE user_id = $2 AND client_slug = $3 AND integration_type = 'google_ads'
                                """,
                                json.dumps(fallback_extra),
                                current_user.user_id,
                                slug,
                            )
                            await conn.execute(
                                """
                                INSERT INTO client_platform_configs
                                    (config_id, user_id, client_slug, client_name, platform, config, is_active)
                                VALUES ($1, $2, $3, $4, 'google_ads', $5::jsonb, true)
                                ON CONFLICT (user_id, client_slug, platform)
                                DO UPDATE SET config = client_platform_configs.config || $5::jsonb, is_active = true
                                """,
                                f"cfg:{slug}:google_ads",
                                current_user.user_id,
                                slug,
                                client["client_name"],
                                json.dumps(fallback_extra),
                            )
            except Exception as e:
                logger.exception("Google Ads fetch failed")
                result["google_ads"] = {"not_connected": False, "error": str(e)}

    # --- GSC ---
    gsc_int = int_by_type.get("google_search_console")
    gsc_cfg = config_by_platform.get("gsc", {})
    # Prefer site_url from client_integrations.extra_config, then client_platform_configs, then first GSC site
    site_url = None
    if gsc_int and gsc_int.get("extra_config"):
        extra = _unwrap_extra(gsc_int["extra_config"])
        if extra.get("site_url"):
            site_url = extra["site_url"]
    if not site_url and isinstance(gsc_cfg, dict) and gsc_cfg.get("site_url"):
        site_url = gsc_cfg["site_url"]

    if not gsc_int:
        result["gsc"] = {"not_connected": True}
    else:
        async with pool.acquire() as conn:
            access_token = await get_valid_access_token(
                conn, current_user.user_id, slug, "google_search_console"
            )
        if not access_token:
            result["gsc"] = {"not_connected": True, "error": "Token refresh failed"}
        else:
            if not site_url:
                site_url = await _get_first_gsc_site(access_token)
            if not site_url:
                result["gsc"] = {"not_connected": True, "error": "Configure site_url in platform config (e.g. https://example.com/)"}
            else:
                try:
                    gsc_data = await fetch_gsc(access_token, site_url, start_str, end_str, slug=slug)
                    result["gsc"] = gsc_data
                except Exception as e:
                    logger.exception("GSC fetch failed")
                    result["gsc"] = {"not_connected": False, "error": str(e)}

    # --- Meta (Facebook/Instagram Ads) ---
    meta_int = int_by_type.get("meta_ads")
    if not meta_int:
        result["meta"] = {"not_connected": True}
    else:
        cfg = meta_int.get("extra_config")
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg) if cfg else {}
            except Exception:
                cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        access_token = cfg.get("access_token")
        ad_account_id = cfg.get("ad_account_id")
        page_access_token = cfg.get("page_access_token")
        instagram_id = cfg.get("instagram_business_id")
        days = max(1, (end_date - start_date).days) if start_date and end_date else 30

        meta_payload: dict[str, Any] = {}
        if ad_account_id and access_token:
            try:
                meta_payload["ads"] = await fetch_meta_ads(access_token, ad_account_id, days)
            except Exception as e:
                logger.exception("Meta Ads fetch failed")
                meta_payload["ads"] = {"error": "meta_api_error", "campaigns": [], "message": str(e)}
        else:
            meta_payload["ads"] = {"error": "no_ad_account_selected", "campaigns": []}

        if page_access_token and instagram_id:
            try:
                meta_payload["instagram"] = await fetch_instagram_insights(
                    page_access_token, instagram_id, days
                )
            except Exception as e:
                logger.exception("Instagram insights fetch failed")
                meta_payload["instagram"] = {"error": "instagram_api_error", "message": str(e)}
        else:
            meta_payload["instagram"] = {"error": "no_instagram_selected"}

        result["meta"] = meta_payload

    # --- Overview (GA4 for users/sessions/conversions, Ads for cost) ---
    # Defensive: never call .get() on a non-dict (e.g. if API returns unexpected types).
    def _safe_dict(v: Any) -> dict:
        return v if isinstance(v, dict) else {}

    total_cost = 0.0
    ga4_block = _safe_dict(result.get("ga4"))
    ads_block = _safe_dict(result.get("google_ads"))
    meta_block = _safe_dict(result.get("meta"))

    if ads_block and not ads_block.get("not_connected"):
        for c in ads_block.get("campaigns") or []:
            if isinstance(c, dict):
                total_cost += float(c.get("cost") or 0) or 0
    if meta_block and not meta_block.get("not_connected"):
        ads = _safe_dict(meta_block.get("ads"))
        if not ads.get("error"):
            total_cost += float(ads.get("total_spend") or 0) or 0

    ga4_kpis = _safe_dict(ga4_block.get("kpis")) if not ga4_block.get("not_connected") else {}
    total_conversions = int(ga4_kpis.get("conversions") or 0) or 0
    total_conv_value = float(ga4_kpis.get("conversion_value") or 0) or 0
    if not total_conversions and ads_block and not ads_block.get("not_connected"):
        for c in ads_block.get("campaigns") or []:
            if isinstance(c, dict):
                total_conversions += int(c.get("conversions") or 0) or 0
                total_conv_value += float(c.get("conversion_value") or 0) or 0
    if meta_block and not meta_block.get("not_connected"):
        ads = _safe_dict(meta_block.get("ads"))
        if not ads.get("error"):
            total_conversions += int(ads.get("total_conversions") or 0) or 0
    cpa = total_cost / total_conversions if total_conversions else 0

    result["overview"] = {
        "users": int(ga4_kpis.get("users") or 0) or 0,
        "sessions": int(ga4_kpis.get("sessions") or 0) or 0,
        "conversions": total_conversions,
        "conversion_value": total_conv_value,
        "total_cost": total_cost,
        "cpa": cpa,
        "conversion_rate": float(ga4_kpis.get("conversion_rate") or 0) or 0,
    }

    return result


@router.get("/{slug}/dashboard/meta")
async def get_meta_dashboard(
    slug: str,
    days: int = Query(30, ge=1, le=90),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Meta dashboard: Ads and optional Instagram/Page data for this client."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT extra_config FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'meta_ads'
            """,
            current_user.user_id,
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Meta not connected")
    cfg = row["extra_config"]
    if isinstance(cfg, str):
        cfg = json.loads(cfg) if cfg else {}
    if not isinstance(cfg, dict):
        cfg = {}
    access_token = cfg.get("access_token")
    ad_account_id = cfg.get("ad_account_id")
    page_access_token = cfg.get("page_access_token")
    instagram_id = cfg.get("instagram_business_id")

    result: dict[str, Any] = {}
    if ad_account_id and access_token:
        result["ads"] = await fetch_meta_ads(access_token, ad_account_id, days)
    else:
        result["ads"] = {"error": "no_ad_account_selected"}

    if page_access_token and instagram_id:
        result["instagram"] = await fetch_instagram_insights(page_access_token, instagram_id, days)
    else:
        result["instagram"] = {"error": "no_instagram_selected"}

    return result


# service_type -> (platform for client_platform_configs, config keys to allow)
SERVICE_CONFIG_PLATFORM = {
    "ga4": ("ga4", ["property_id"]),
    "google_search_console": ("gsc", ["site_url"]),
    "google_ads": ("google_ads", ["customer_id", "login_customer_id"]),
    "meta_ads": ("meta_ads", ["ad_account_id"]),
}


@router.patch("/{slug}/integrations/{service_type}/config")
async def save_integration_config(
    slug: str,
    service_type: str,
    body: IntegrationConfigBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Sla geselecteerde property/account op in extra_config en client_platform_configs."""
    if service_type not in SERVICE_CONFIG_PLATFORM:
        raise HTTPException(status_code=400, detail="Invalid service_type")
    platform, allowed_keys = SERVICE_CONFIG_PLATFORM[service_type]
    config_dict = body.model_dump(exclude_none=True)
    config_dict = {k: v for k, v in config_dict.items() if k in allowed_keys}
    if not config_dict:
        raise HTTPException(status_code=400, detail="No valid config provided")

    pool = await get_db()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT slug, client_name FROM clients WHERE user_id = $1 AND slug = $2",
            current_user.user_id,
            slug,
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        row = await conn.fetchrow(
            """
            SELECT integration_id, extra_config
            FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type = $3
            """,
            current_user.user_id,
            slug,
            service_type,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Integration not found")

        extra = _unwrap_extra(row["extra_config"])
        extra.update(config_dict)
        extra_json = json.dumps(extra)
        if service_type == "google_ads" and config_dict.get("login_customer_id"):
            logger.info(
                "Google Ads config saved: slug=%s, customer_id=%s, login_customer_id=%s",
                slug, config_dict.get("customer_id"), config_dict.get("login_customer_id"),
            )

        await conn.execute(
            """
            UPDATE client_integrations
            SET extra_config = $1::jsonb, updated_at = now()
            WHERE user_id = $2 AND client_slug = $3 AND integration_type = $4
            """,
            extra_json,
            current_user.user_id,
            slug,
            service_type,
        )
        config_id = f"cfg:{slug}:{platform}"
        config_json = json.dumps(config_dict)
        await conn.execute(
            """
            INSERT INTO client_platform_configs
                (config_id, user_id, client_slug, client_name, platform, config, is_active)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, true)
            ON CONFLICT (user_id, client_slug, platform)
            DO UPDATE SET config = client_platform_configs.config || $6::jsonb, is_active = true
            """,
            config_id,
            current_user.user_id,
            slug,
            client["client_name"],
            platform,
            config_json,
        )
    return {"status": "ok", "extra_config": extra}


@router.get("/{slug}")
async def get_client(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get client detail and all platform configs."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            """
            SELECT client_id, slug, client_name, description, is_active, created_at
            FROM clients
            WHERE user_id = $1 AND slug = $2
            """,
            current_user.user_id,
            slug,
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        configs = await conn.fetch(
            """
            SELECT config_id, platform, config, is_active, created_at
            FROM client_platform_configs
            WHERE user_id = $1 AND client_slug = $2
            ORDER BY platform
            """,
            current_user.user_id,
            slug,
        )

    return {
        "client_id": client["client_id"],
        "slug": client["slug"],
        "client_name": client["client_name"],
        "description": client["description"],
        "is_active": client["is_active"],
        "created_at": client["created_at"].isoformat() if client["created_at"] else None,
        "platform_configs": [
            {
                "config_id": r["config_id"],
                "platform": r["platform"],
                "config": r["config"] or {},
                "is_active": r["is_active"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in configs
        ],
    }


@router.post("/{slug}/platforms")
async def upsert_platform_config(
    slug: str,
    body: PlatformConfigBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Add or update platform config for a client."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT slug, client_name FROM clients WHERE user_id = $1 AND slug = $2",
            current_user.user_id,
            slug,
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        config_id = f"cfg:{slug}:{body.platform}"
        config_json = json.dumps(body.config) if isinstance(body.config, dict) else "{}"

        await conn.execute(
            """
            INSERT INTO client_platform_configs
                (config_id, user_id, client_slug, client_name, platform, config, is_active)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, true)
            ON CONFLICT (user_id, client_slug, platform)
            DO UPDATE SET config = EXCLUDED.config, is_active = true
            """,
            config_id,
            current_user.user_id,
            slug,
            client["client_name"],
            body.platform,
            config_json,
        )
    return {"status": "ok", "slug": slug, "platform": body.platform}


@router.delete("/{slug}/platforms/{platform}")
async def delete_platform_config(
    slug: str,
    platform: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Remove platform config for a client."""
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM client_platform_configs
            WHERE user_id = $1 AND client_slug = $2 AND platform = $3
            """,
            current_user.user_id,
            slug,
            platform,
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Platform config not found")
    return {"status": "ok", "slug": slug, "platform": platform}


# --- Client knowledge / datasources ---


async def _client_id_for_slug(conn, slug: str, user_id) -> str:
    """Return client_id for slug and user; raise 404 if not found."""
    row = await conn.fetchrow(
        "SELECT client_id FROM clients WHERE user_id = $1 AND slug = $2",
        user_id,
        slug,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    return row["client_id"]


@router.post("/{slug}/datasources")
async def create_datasource(
    slug: str,
    body: DatasourceCreateBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Create a knowledge datasource for the client. Returns datasource_id and status pending."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client_id = await _client_id_for_slug(conn, slug, current_user.user_id)
        row = await conn.fetchrow(
            """
            INSERT INTO client_datasources
            (client_id, name, source_type, domain, sitemap_url, raw_text, feed_url, feed_splitting_tag, feed_identifier_tag, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')
            RETURNING id, status
            """,
            client_id,
            body.name,
            body.source_type,
            body.domain,
            body.sitemap_url,
            body.raw_text,
            body.feed_url,
            body.feed_splitting_tag,
            body.feed_identifier_tag,
        )
    return {"datasource_id": row["id"], "status": row["status"]}


@router.get("/{slug}/datasources")
async def list_datasources(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List all datasources for the client."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client_id = await _client_id_for_slug(conn, slug, current_user.user_id)
        rows = await conn.fetch(
            """
            SELECT id, name, source_type, status, chunks_created, finished_at, file_name, error_detail
            FROM client_datasources
            WHERE client_id = $1
            ORDER BY created_at DESC
            """,
            client_id,
        )
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "source_type": r["source_type"],
            "status": r["status"],
            "chunks_created": r["chunks_created"],
            "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
            "file_name": r["file_name"],
            "error_detail": r["error_detail"],
        }
        for r in rows
    ]


@router.delete("/{slug}/datasources/{datasource_id:int}")
async def delete_datasource(
    slug: str,
    datasource_id: int,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Remove datasource and all its chunks."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client_id = await _client_id_for_slug(conn, slug, current_user.user_id)
        result = await conn.execute(
            "DELETE FROM client_datasources WHERE id = $1 AND client_id = $2",
            datasource_id,
            client_id,
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Datasource not found")
    return {"status": "ok"}


async def _process_datasource_background(
    client_id: str,
    datasource_id: int,
    source_type: str,
    domain: Optional[str],
    sitemap_url: Optional[str],
    raw_text: Optional[str],
    feed_url: Optional[str],
    feed_splitting_tag: Optional[str],
    feed_identifier_tag: Optional[str],
) -> None:
    """Background: run crawler, text, or feed processor."""
    pool = await get_db()
    try:
        if source_type == "website_crawl" and domain:
            crawler = ClientCrawler(client_id, datasource_id, pool)
            await crawler.run_crawl(domain)
        elif source_type == "website_sitemap" and sitemap_url:
            crawler = ClientCrawler(client_id, datasource_id, pool)
            await crawler.run_sitemap(sitemap_url)
        elif source_type == "text" and raw_text is not None:
            proc = ClientTextProcessor(client_id, datasource_id, pool)
            await proc.process(raw_text, "Tekst")
        elif source_type == "product_feed" and feed_url and feed_splitting_tag and feed_identifier_tag:
            proc = ClientFeedProcessor(client_id, datasource_id, pool)
            await proc.process(feed_url, feed_splitting_tag, feed_identifier_tag)
        else:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE client_datasources SET status = 'failed', error_detail = $1 WHERE id = $2",
                    "Missing parameters for source_type " + source_type,
                    datasource_id,
                )
    except Exception as e:
        logger.exception("client knowledge process failed: %s", e)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE client_datasources SET status = 'failed', error_detail = $1 WHERE id = $2",
                str(e),
                datasource_id,
            )


def _sitemap_filename(url: str) -> str:
    """Extract filename from sitemap URL for child datasource name."""
    path = (urlparse(url).path or "").strip("/")
    return path.split("/")[-1] or "sitemap.xml"


@router.post("/{slug}/datasources/{datasource_id:int}/process")
async def start_process(
    slug: str,
    datasource_id: int,
    background_tasks: BackgroundTasks,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Start processing (crawl, sitemap, text, or product_feed). Returns immediately; status via GET status."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client_id = await _client_id_for_slug(conn, slug, current_user.user_id)
        row = await conn.fetchrow(
            """
            SELECT id, source_type, domain, sitemap_url, raw_text, feed_url, feed_splitting_tag, feed_identifier_tag
            FROM client_datasources
            WHERE id = $1 AND client_id = $2
            """,
            datasource_id,
            client_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Datasource not found")

    if row["source_type"] == "website_sitemap" and row["sitemap_url"]:
        kind, sub_urls = await get_sitemap_structure(row["sitemap_url"])
        if kind == "index" and sub_urls:
            async with pool.acquire() as conn:
                for sub_url in sub_urls:
                    name = _sitemap_filename(sub_url)
                    child_row = await conn.fetchrow(
                        """
                        INSERT INTO client_datasources
                        (client_id, name, source_type, sitemap_url, status)
                        VALUES ($1, $2, 'website_sitemap', $3, 'pending')
                        RETURNING id
                        """,
                        client_id,
                        name,
                        sub_url,
                    )
                    if child_row:
                        background_tasks.add_task(
                            _process_datasource_background,
                            client_id,
                            child_row["id"],
                            "website_sitemap",
                            None,
                            sub_url,
                            None,
                            None,
                            None,
                            None,
                        )
                await conn.execute(
                    """
                    UPDATE client_datasources
                    SET status = 'done', finished_at = now(), updated_at = now(),
                        error_detail = $2, chunks_created = 0
                    WHERE id = $1
                    """,
                    datasource_id,
                    f"Sitemap index: {len(sub_urls)} sub-sitemaps aangemaakt als aparte bronnen.",
                )
            return {"status": "processing"}

    background_tasks.add_task(
        _process_datasource_background,
        client_id,
        datasource_id,
        row["source_type"],
        row["domain"],
        row["sitemap_url"],
        row["raw_text"],
        row["feed_url"],
        row["feed_splitting_tag"],
        row["feed_identifier_tag"],
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_datasources SET status = 'processing' WHERE id = $1",
            datasource_id,
        )
    return {"status": "processing"}


@router.post("/{slug}/datasources/{datasource_id:int}/upload")
async def upload_datasource_file(
    slug: str,
    datasource_id: int,
    background_tasks: BackgroundTasks,
    current_user: TokenPayload = Depends(get_current_user),
    file: UploadFile = File(...),
):
    """Upload PDF or CSV; start processing in background. Returns status processing."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client_id = await _client_id_for_slug(conn, slug, current_user.user_id)
        row = await conn.fetchrow(
            "SELECT id, source_type FROM client_datasources WHERE id = $1 AND client_id = $2",
            datasource_id,
            client_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Datasource not found")
        if row["source_type"] != "file":
            raise HTTPException(status_code=400, detail="Datasource is not a file type")

    name = file.filename or "upload"
    ext = name.lower().split(".")[-1] if "." in name else ""
    if ext not in ("pdf", "csv"):
        raise HTTPException(status_code=400, detail="Only PDF or CSV allowed")

    content = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="." + ext)
    tmp.write(content)
    tmp.close()
    tmp_path = tmp.name

    async def _run_file() -> None:
        pool_inner = await get_db()
        try:
            with open(tmp_path, "rb") as f:
                data = f.read()
            proc = ClientFileProcessor(client_id, datasource_id, pool_inner)
            if ext == "pdf":
                await proc.process_pdf(data, name)
            else:
                await proc.process_csv(data, name)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    background_tasks.add_task(_run_file)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_datasources SET status = 'processing', file_name = $1, file_type = $2 WHERE id = $3",
            name,
            ext,
            datasource_id,
        )
    return {"status": "processing", "file_name": name}


@router.get("/{slug}/datasources/{datasource_id:int}/status")
async def get_datasource_status(
    slug: str,
    datasource_id: int,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Poll processing status."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client_id = await _client_id_for_slug(conn, slug, current_user.user_id)
        row = await conn.fetchrow(
            """
            SELECT status, pages_found, pages_processed, chunks_created, error_detail
            FROM client_datasources
            WHERE id = $1 AND client_id = $2
            """,
            datasource_id,
            client_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Datasource not found")

    total = row["pages_found"] or 0
    done = row["pages_processed"] or 0
    percent = (int((done / total * 100)) if total else 0) if row["status"] == "processing" else 100
    return {
        "status": row["status"],
        "pages_found": row["pages_found"],
        "pages_processed": row["pages_processed"],
        "chunks_created": row["chunks_created"],
        "error_detail": row["error_detail"],
        "percent": percent,
    }


@router.get("/{slug}/knowledge")
async def get_client_knowledge_overview(
    slug: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Overview: chunks_total and per-datasource summary."""
    pool = await get_db()
    async with pool.acquire() as conn:
        client_id = await _client_id_for_slug(conn, slug, current_user.user_id)
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM client_knowledge WHERE client_id = $1 AND is_active = true",
            client_id,
        )
        rows = await conn.fetch(
            """
            SELECT d.name, d.source_type, COUNT(k.id) AS chunks, MAX(k.added_at) AS last_updated
            FROM client_datasources d
            LEFT JOIN client_knowledge k ON k.datasource_id = d.id AND k.is_active = true
            WHERE d.client_id = $1
            GROUP BY d.id, d.name, d.source_type
            ORDER BY d.name
            """,
            client_id,
        )
    return {
        "chunks_total": total or 0,
        "datasources": [
            {
                "name": r["name"],
                "type": r["source_type"],
                "chunks": r["chunks"],
                "last_updated": r["last_updated"].isoformat() if r["last_updated"] else None,
            }
            for r in rows
        ],
    }
