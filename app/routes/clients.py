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
    _refresh_access_token,
    fetch_ga4,
    fetch_gsc,
    fetch_google_ads_via_gaql,
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
        row = await conn.fetchrow(
            """
            SELECT api_key_encrypted, extra_config
            FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'ga4'
            """,
            current_user.user_id,
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="GA4 not connected for this client")
    refresh = _get_refresh_token(row["api_key_encrypted"], row["extra_config"])
    if not refresh:
        raise HTTPException(status_code=400, detail="No refresh token")
    access_token = await _refresh_access_token(refresh)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed")
    try:
        props = await list_ga4_properties(access_token)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
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
        raise HTTPException(status_code=400, detail="No refresh token")
    try:
        accounts = await list_google_ads_accounts(refresh)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return accounts


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
        row = await conn.fetchrow(
            """
            SELECT api_key_encrypted, extra_config
            FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type = 'google_search_console'
            """,
            current_user.user_id,
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Search Console not connected for this client")
    refresh = _get_refresh_token(row["api_key_encrypted"], row["extra_config"])
    if not refresh:
        raise HTTPException(status_code=400, detail="No refresh token")
    access_token = await _refresh_access_token(refresh)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed")
    try:
        sites = await list_gsc_sites(access_token)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
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

    if not ga4_int:
        result["ga4"] = {"not_connected": True}
    else:
        refresh = _get_refresh_token(ga4_int["api_key_encrypted"], ga4_int["extra_config"])
        if not refresh:
            result["ga4"] = {"not_connected": True}
        else:
            access_token = await _refresh_access_token(refresh)
            if not access_token:
                result["ga4"] = {"not_connected": True, "error": "Token refresh failed"}
            else:
                if not property_id:
                    property_id = await _get_first_ga4_property(access_token)
                if not property_id:
                    result["ga4"] = {"not_connected": True, "error": "No GA4 property found"}
                else:
                    try:
                        ga4_data = await fetch_ga4(
                            access_token, property_id, start_str, end_str, channel, device
                        )
                        result["ga4"] = ga4_data
                    except Exception as e:
                        logger.exception("GA4 fetch failed")
                        result["ga4"] = {"not_connected": False, "error": str(e)}

    # --- Google Ads ---
    ads_int = int_by_type.get("google_ads")
    ads_cfg = config_by_platform.get("google_ads", {})
    customer_id = ads_cfg.get("customer_id") if isinstance(ads_cfg, dict) else None

    if not ads_int:
        result["google_ads"] = {"not_connected": True}
    else:
        refresh = _get_refresh_token(ads_int["api_key_encrypted"], ads_int["extra_config"])
        if not refresh:
            result["google_ads"] = {"not_connected": True}
        else:
            if not customer_id:
                customer_id = await _get_first_google_ads_customer(refresh)
            if not customer_id:
                result["google_ads"] = {"not_connected": True, "error": "Configure customer_id in platform config or no accessible accounts"}
            else:
                try:
                    ads_data = await fetch_google_ads_via_gaql(refresh, customer_id, start_str, end_str)
                    if ads_data.get("not_implemented") or ads_data.get("not_configured"):
                        result["google_ads"] = {"not_connected": True, "error": ads_data.get("error", "Google Ads not configured")}
                    elif ads_data.get("error"):
                        result["google_ads"] = {"not_connected": False, "error": ads_data["error"]}
                    else:
                        result["google_ads"] = ads_data
                except Exception as e:
                    logger.exception("Google Ads fetch failed")
                    result["google_ads"] = {"not_connected": False, "error": str(e)}

    # --- GSC ---
    gsc_int = int_by_type.get("google_search_console")
    gsc_cfg = config_by_platform.get("gsc", {})
    site_url = gsc_cfg.get("site_url") if isinstance(gsc_cfg, dict) else None

    if not gsc_int:
        result["gsc"] = {"not_connected": True}
    else:
        refresh = _get_refresh_token(gsc_int["api_key_encrypted"], gsc_int["extra_config"])
        if not refresh:
            result["gsc"] = {"not_connected": True}
        else:
            access_token = await _refresh_access_token(refresh)
            if not access_token:
                result["gsc"] = {"not_connected": True, "error": "Token refresh failed"}
            else:
                if not site_url:
                    site_url = await _get_first_gsc_site(access_token)
                if not site_url:
                    result["gsc"] = {"not_connected": True, "error": "Configure site_url in platform config (e.g. https://example.com/)"}
                else:
                    try:
                        gsc_data = await fetch_gsc(access_token, site_url, start_str, end_str)
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
