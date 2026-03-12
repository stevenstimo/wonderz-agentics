"""Clients API — client management and platform configs.

Uses clients.slug as identifier. client_platform_configs stores platform-specific IDs per client.
"""

import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user
from app.services.dashboard import (
    _get_first_ga4_property,
    _get_first_google_ads_customer,
    _get_first_gsc_site,
    _get_refresh_token,
    fetch_ga4,
    fetch_gsc,
    fetch_google_ads_via_gaql,
    get_valid_access_token,
    list_ga4_properties,
    list_google_ads_accounts,
    list_gsc_sites,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clients", tags=["clients"])


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
    """Config for Google integration: property_id (ga4), site_url (gsc), customer_id + login_customer_id (google_ads)."""
    property_id: Optional[str] = None
    site_url: Optional[str] = None
    customer_id: Optional[str] = None
    login_customer_id: Optional[str] = None


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
            if "agency_clients_user_id_slug_key" in str(e) or "unique" in str(e).lower():
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
    refresh = _get_refresh_token(row["api_key_encrypted"], row["extra_config"])
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
            WHERE user_id = $1 AND client_slug = $2 AND integration_type IN ('ga4', 'google_ads', 'google_search_console')
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
    config_by_platform = {r["platform"]: (r["config"] or {}) for r in configs}

    result: dict[str, Any] = {
        "overview": None,
        "ga4": None,
        "google_ads": None,
        "gsc": None,
    }

    # --- GA4 ---
    ga4_int = int_by_type.get("ga4")
    ga4_cfg = config_by_platform.get("ga4", {})
    property_id = ga4_cfg.get("property_id") if isinstance(ga4_cfg, dict) else None
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
    extra_config = ads_int.get("extra_config") if ads_int else None
    if isinstance(extra_config, str):
        try:
            extra_config = json.loads(extra_config)
        except Exception:
            extra_config = {}
    extra_config = extra_config or {}
    customer_id = (
        extra_config.get("google_ads_customer_id")
        or extra_config.get("customer_id")
        or (ads_cfg.get("customer_id") if isinstance(ads_cfg, dict) else None)
    )
    ads_used_fallback = False

    if not ads_int:
        result["google_ads"] = {"not_connected": True}
    else:
        refresh = _get_refresh_token(ads_int["api_key_encrypted"], ads_int["extra_config"])
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

    # --- Overview (GA4 for users/sessions/conversions, Ads for cost) ---
    total_cost = 0.0
    if result.get("google_ads") and not result["google_ads"].get("not_connected"):
        for c in result["google_ads"].get("campaigns", []):
            total_cost += c.get("cost", 0) or 0
    ga4_kpis = result.get("ga4", {}).get("kpis", {}) if result.get("ga4") and not result["ga4"].get("not_connected") else {}
    total_conversions = ga4_kpis.get("conversions", 0) or 0
    total_conv_value = ga4_kpis.get("conversion_value", 0) or 0
    if not total_conversions and result.get("google_ads") and not result["google_ads"].get("not_connected"):
        for c in result["google_ads"].get("campaigns", []):
            total_conversions += c.get("conversions", 0) or 0
            total_conv_value += c.get("conversion_value", 0) or 0
    cpa = total_cost / total_conversions if total_conversions else 0

    result["overview"] = {
        "users": ga4_kpis.get("users", 0),
        "sessions": ga4_kpis.get("sessions", 0),
        "conversions": total_conversions,
        "conversion_value": total_conv_value,
        "total_cost": total_cost,
        "cpa": cpa,
        "conversion_rate": ga4_kpis.get("conversion_rate", 0),
    }

    return result


# service_type -> (platform for client_platform_configs, config keys to allow)
SERVICE_CONFIG_PLATFORM = {
    "ga4": ("ga4", ["property_id"]),
    "google_search_console": ("gsc", ["site_url"]),
    "google_ads": ("google_ads", ["customer_id", "login_customer_id"]),
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

        extra = row["extra_config"] or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception:
                extra = {}
        extra = dict(extra)
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
