"""Integrations API — per-user API keys and credentials.

Uses get_current_user for user_id from JWT. integration_type from path (e.g. klaviyo).
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user
from app.services.dashboard import list_gsc_sites

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# Google OAuth scopes per service — elk platform apart verbinden met eigen account
GOOGLE_SCOPES_PER_SERVICE = {
    "ga4": [
        "https://www.googleapis.com/auth/analytics.readonly",
        "https://www.googleapis.com/auth/analytics.edit",
    ],
    "google_search_console": [
        "https://www.googleapis.com/auth/webmasters.readonly",
    ],
    "google_ads": [
        "https://www.googleapis.com/auth/adwords",
    ],
    "business_profile": [
        "https://www.googleapis.com/auth/business.manage",
    ],
    "youtube": [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ],
    "merchant_center": [
        "https://www.googleapis.com/auth/content",
    ],
    "sheets": [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ],
}
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_INTEGRATION_TYPES = ["ga4", "google_ads", "google_search_console"]
GOOGLE_OAUTH_INTEGRATION_TYPES = [
    "ga4",
    "google_ads",
    "google_search_console",
    "business_profile",
    "youtube",
    "merchant_center",
    "sheets",
]
ALLOWED_GOOGLE_SERVICE_TYPES = frozenset(GOOGLE_OAUTH_INTEGRATION_TYPES)


def _create_oauth_state(
    user_id: str,
    secret: str,
    return_to: Optional[str] = None,
    client_slug: Optional[str] = None,
    service_type: Optional[str] = None,
) -> str:
    """Create signed state for CSRF protection. Expires in 10 min."""
    payload = {"user_id": user_id, "exp": int(time.time()) + 600}
    if return_to:
        payload["return_to"] = return_to
    if client_slug:
        payload["client_slug"] = client_slug
    if service_type:
        payload["service_type"] = service_type
    payload = json.dumps(payload)
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(
        secret.encode() if isinstance(secret, str) else secret,
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def _verify_oauth_state(
    state: str, secret: str
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Verify state and return (user_id, return_to, client_slug, service_type)
    or (None, None, None, None)."""
    try:
        parts = state.split(".")
        if len(parts) != 2:
            return (None, None, None, None)
        payload_b64, sig = parts
        pad = 4 - len(payload_b64) % 4
        if pad != 4:
            payload_b64 += "=" * pad
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
        if payload.get("exp", 0) < time.time():
            return (None, None, None, None)
        expected = hmac.new(
            secret.encode() if isinstance(secret, str) else secret,
            parts[0].encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return (None, None, None, None)
        return (
            payload.get("user_id"),
            payload.get("return_to"),
            payload.get("client_slug"),
            payload.get("service_type"),
        )
    except Exception as e:
        logger.warning(f"State verification failed: {e}")
        return (None, None, None, None)


class GoogleAuthUrlRequest(BaseModel):
    return_to: Optional[str] = None
    client_slug: Optional[str] = None
    """If set, OAuth stores only that integration. If omitted, legacy bundle: GA4 + GSC + Google Ads."""
    service_type: Optional[str] = None

    @field_validator("service_type")
    @classmethod
    def validate_auth_service_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_GOOGLE_SERVICE_TYPES:
            raise ValueError("Invalid service_type")
        return v


class GoogleRefreshRequest(BaseModel):
    client_slug: str = Field(..., min_length=1)
    service_type: Optional[str] = None

    @field_validator("service_type")
    @classmethod
    def validate_refresh_service_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_GOOGLE_SERVICE_TYPES:
            raise ValueError("Invalid service_type")
        return v


async def _refresh_google_token(refresh_token: str) -> tuple[Optional[str], int]:
    """Exchange refresh_token for access_token. Returns (access_token, expires_in)."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None, 0
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        logger.warning("Token refresh failed: status=%s body=%s", resp.status_code, resp.text[:300])
        return None, 0
    data = resp.json()
    return data.get("access_token"), data.get("expires_in", 3600)


@router.post("/google/refresh")
async def google_refresh(
    body: GoogleRefreshRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Refresh Google OAuth tokens for a client. Returns ok if at least one token refreshed.
    needs_reauth=True when refresh_token is missing or invalid — frontend should start full OAuth flow."""
    pool = await get_db()

    def get_refresh_token(row):
        extra = row["extra_config"]
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception:
                extra = {}
        refresh = (extra or {}).get("refresh_token")
        if refresh:
            return refresh
        return row["api_key_encrypted"]

    types_filter = (
        [body.service_type]
        if body.service_type
        else list(GOOGLE_OAUTH_INTEGRATION_TYPES)
    )
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT integration_type, api_key_encrypted, extra_config
            FROM client_integrations
            WHERE user_id = $1 AND client_slug = $2 AND integration_type = ANY($3)
            """,
            current_user.user_id,
            body.client_slug,
            types_filter,
        )
    if not rows:
        raise HTTPException(status_code=404, detail="No Google integrations for this client")

    refreshed = 0
    needs_reauth = False
    for row in rows:
        refresh = get_refresh_token(row)
        if not refresh:
            needs_reauth = True
            continue
        access_token, expires_in = await _refresh_google_token(refresh)
        if access_token:
            extra = row["extra_config"]
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except Exception:
                    extra = {}
            extra = dict(extra or {})
            extra["access_token"] = access_token
            extra["expires_at"] = int(time.time()) + expires_in
            extra["oauth_connected"] = True
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE client_integrations
                    SET extra_config = $4::jsonb, updated_at = now()
                    WHERE user_id = $1 AND client_slug = $2 AND integration_type = $3
                    """,
                    current_user.user_id,
                    body.client_slug,
                    row["integration_type"],
                    json.dumps(extra),
                )
            refreshed += 1
        else:
            needs_reauth = True

    if refreshed == 0:
        # Frontend should start full OAuth flow via POST /google/auth-url
        return {
            "ok": False,
            "refreshed": 0,
            "needs_reauth": True,
        }
    return {"ok": True, "refreshed": refreshed, "needs_reauth": needs_reauth}


@router.post("/google/auth-url")
async def google_auth_url(
    body: GoogleAuthUrlRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Generate Google OAuth URL for a specific service, or legacy bundle (GA4 + GSC + Ads) when service_type omitted."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured (GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI)",
        )
    if body.service_type:
        scopes = GOOGLE_SCOPES_PER_SERVICE.get(body.service_type)
        if not scopes:
            raise HTTPException(status_code=400, detail="Invalid service_type")
        state_service: Optional[str] = body.service_type
    else:
        scopes_flat: list[str] = []
        for t in GOOGLE_INTEGRATION_TYPES:
            scopes_flat.extend(GOOGLE_SCOPES_PER_SERVICE.get(t, []))
        seen: set[str] = set()
        scopes = []
        for s in scopes_flat:
            if s not in seen:
                seen.add(s)
                scopes.append(s)
        state_service = None
    secret = os.getenv("SUPABASE_JWT_SECRET", "fallback-secret-change-me")
    return_to = body.return_to if body.return_to else None
    client_slug = body.client_slug if body.client_slug else None
    state = _create_oauth_state(
        current_user.user_id, secret, return_to, client_slug, state_service
    )
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    qs = urlencode(params)
    url = f"{GOOGLE_AUTH_URL}?{qs}"
    return {"url": url}


def _oauth_redirect_url(
    frontend_base: str,
    client_slug: Optional[str],
    success: bool,
    param: str = "",
    connected: str = "google",
) -> str:
    """Build redirect URL: client-specific /clients/{slug}/integrations or fallback /integrations."""
    base = frontend_base.rstrip("/")
    if client_slug:
        path = f"/clients/{client_slug}/integrations"
    else:
        path = "/integrations"
    if success:
        return f"{base}{path}?connected={connected}"
    return f"{base}{path}?error={param}" if param else f"{base}{path}"


@router.get("/google/callback")
async def google_oauth_callback(code: Optional[str] = None, state: Optional[str] = None):
    """OAuth callback from Google. Exchange code for tokens, store for ga4/google_ads/gsc, redirect to client-specific integrations page."""
    frontend_base = os.getenv("FRONTEND_BASE_URL", "https://wonderz-agentic.exe.xyz")

    if not code or not state:
        logger.warning("Google callback missing code or state")
        return RedirectResponse(url=_oauth_redirect_url(frontend_base, None, False, "missing_params"), status_code=302)

    secret = os.getenv("SUPABASE_JWT_SECRET", "fallback-secret-change-me")
    user_id, return_to, client_slug, service_type = _verify_oauth_state(state, secret)
    logger.info(
        "Google OAuth callback: state parsed user_id=%s return_to=%s client_slug=%s service_type=%s",
        user_id,
        return_to,
        client_slug,
        service_type,
    )
    if not user_id:
        logger.warning("Google callback invalid state")
        return RedirectResponse(url=_oauth_redirect_url(frontend_base, client_slug, False, "invalid_state"), status_code=302)

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        logger.error("Google OAuth not configured")
        return RedirectResponse(url=_oauth_redirect_url(frontend_base, client_slug, False, "config"), status_code=302)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        logger.warning(f"Google token exchange failed: {resp.status_code} {resp.text}")
        return RedirectResponse(url=_oauth_redirect_url(frontend_base, client_slug, False, "token_exchange"), status_code=302)

    data = resp.json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        logger.warning("Google did not return refresh_token (try prompt=consent)")
    # Store refresh_token as main credential; use it for all three integration types
    token_to_store = refresh_token or access_token
    if not token_to_store:
        return RedirectResponse(url=_oauth_redirect_url(frontend_base, client_slug, False, "no_tokens"), status_code=302)

    expires_in = data.get("expires_in", 3600)
    expires_at = int(time.time()) + expires_in

    # Extract google_email from id_token for display
    google_email = None
    id_token = data.get("id_token", "")
    if id_token:
        try:
            payload_part = id_token.split(".")[1]
            pad = 4 - len(payload_part) % 4
            if pad != 4:
                payload_part += "=" * pad
            id_payload = json.loads(base64.urlsafe_b64decode(payload_part).decode())
            google_email = id_payload.get("email")
        except Exception:
            pass

    logger.info(
        "Google OAuth callback: token exchange ok, has_refresh=%s scope=%s",
        bool(refresh_token),
        data.get("scope", "")[:80],
    )

    # Backward compat: als service_type ontbreekt, sla op voor alle drie
    integration_types = [service_type] if service_type else GOOGLE_INTEGRATION_TYPES

    # Build extra_config: access_token, expires_at, refresh_token, google_email
    extra_config = {"access_token": access_token, "expires_at": expires_at, "oauth_connected": True}
    if refresh_token:
        extra_config["refresh_token"] = refresh_token
    if google_email:
        extra_config["google_email"] = google_email

    pool = await get_db()
    async with pool.acquire() as conn:
        for integration_type in integration_types:
            integration_id = (
                f"int:{user_id}:{client_slug}:{integration_type}"
                if client_slug
                else f"int:{user_id}:{integration_type}"
            )
            # Upsert with COALESCE for refresh_token — Google may not return new refresh_token on reconnection
            if client_slug:
                refresh_to_store = refresh_token or ""
                await conn.execute(
                    """
                    INSERT INTO client_integrations
                        (integration_id, user_id, client_slug, integration_type, api_key_encrypted, extra_config, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())
                    ON CONFLICT (user_id, client_slug, integration_type) DO UPDATE SET
                        api_key_encrypted = COALESCE(NULLIF($7, ''), client_integrations.api_key_encrypted),
                        extra_config = client_integrations.extra_config || jsonb_build_object(
                            'access_token', EXCLUDED.extra_config->>'access_token',
                            'expires_at', COALESCE((EXCLUDED.extra_config->>'expires_at')::int, (EXTRACT(EPOCH FROM now())::int + 3600)),
                            'oauth_connected', true,
                            'refresh_token', COALESCE(NULLIF(EXCLUDED.extra_config->>'refresh_token', ''), client_integrations.extra_config->>'refresh_token'),
                            'google_email', COALESCE(EXCLUDED.extra_config->>'google_email', client_integrations.extra_config->>'google_email')
                        ),
                        updated_at = now()
                    """,
                    integration_id,
                    user_id,
                    client_slug,
                    integration_type,
                    token_to_store,
                    json.dumps(extra_config),
                    refresh_to_store,
                )
            else:
                existing = await conn.fetchrow(
                    """
                    SELECT integration_id, api_key_encrypted, extra_config FROM client_integrations
                    WHERE user_id = $1 AND client_slug IS NULL AND integration_type = $2
                    """,
                    user_id,
                    integration_type,
                )
                if existing:
                    # COALESCE: keep existing refresh_token when Google didn't return new one
                    old_extra = existing["extra_config"] or {}
                    if isinstance(old_extra, str):
                        try:
                            old_extra = json.loads(old_extra)
                        except Exception:
                            old_extra = {}
                    merged_refresh = refresh_token or old_extra.get("refresh_token") or existing["api_key_encrypted"]
                    merged_extra = {"access_token": access_token, "expires_at": expires_at, "oauth_connected": True}
                    if merged_refresh:
                        merged_extra["refresh_token"] = merged_refresh
                    if google_email:
                        merged_extra["google_email"] = google_email
                    token_final = refresh_token or existing["api_key_encrypted"] or token_to_store
                    await conn.execute(
                        """
                        UPDATE client_integrations
                        SET api_key_encrypted = $3, extra_config = $4::jsonb, updated_at = now()
                        WHERE user_id = $1 AND client_slug IS NULL AND integration_type = $2
                        """,
                        user_id,
                        integration_type,
                        token_final,
                        json.dumps(merged_extra),
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO client_integrations
                            (integration_id, user_id, client_slug, integration_type, api_key_encrypted, extra_config, updated_at)
                        VALUES ($1, $2, NULL, $3, $4, $5::jsonb, now())
                        """,
                        integration_id,
                        user_id,
                        integration_type,
                        token_to_store,
                        json.dumps(extra_config),
                    )

    types_logged = list(integration_types) if integration_types else list(GOOGLE_INTEGRATION_TYPES)
    async with pool.acquire() as conn:
        if client_slug:
            saved = await conn.fetch(
                """
                SELECT integration_id, user_id, client_slug, integration_type, updated_at
                FROM client_integrations
                WHERE user_id = $1 AND client_slug = $2 AND integration_type = ANY($3::text[])
                ORDER BY integration_type
                """,
                user_id,
                client_slug,
                types_logged,
            )
        else:
            saved = await conn.fetch(
                """
                SELECT integration_id, user_id, client_slug, integration_type, updated_at
                FROM client_integrations
                WHERE user_id = $1 AND client_slug IS NULL AND integration_type = ANY($2::text[])
                ORDER BY integration_type
                """,
                user_id,
                types_logged,
            )
    logger.info(
        "Google OAuth callback: saved %d records for user_id=%s client_slug=%s: %s",
        len(saved),
        user_id,
        client_slug,
        [(r["integration_id"], r["integration_type"]) for r in saved],
    )

    # After GSC OAuth for a client: fetch site list and store site_url in extra_config
    if client_slug and "google_search_console" in integration_types:
        try:
            sites = await list_gsc_sites(access_token)
            if sites:
                primary_url = sites[0].get("site_url", "")
                all_urls = [s.get("site_url", "") for s in sites if s.get("site_url")]
                gsc_extra = {"site_url": primary_url}
                if all_urls:
                    gsc_extra["gsc_sites"] = all_urls
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE client_integrations
                        SET extra_config = extra_config || $1::jsonb, updated_at = now()
                        WHERE user_id = $2 AND client_slug = $3 AND integration_type = 'google_search_console'
                        """,
                        json.dumps(gsc_extra),
                        user_id,
                        client_slug,
                    )
                logger.info("GSC site_url saved for user_id=%s client_slug=%s: %s", user_id, client_slug, primary_url)
        except Exception as e:
            logger.warning("GSC site_url ophalen mislukt (niet fataal): %s", e)

    # Prefer return_to from state, else client-specific or generic integrations
    connected_param = service_type or "google"
    if return_to:
        redirect_url = f"{frontend_base.rstrip('/')}{return_to}?connected={connected_param}"
    else:
        redirect_url = _oauth_redirect_url(frontend_base, client_slug, True, connected=connected_param)
    logger.info("Google OAuth callback: redirecting to %s", redirect_url)
    return RedirectResponse(url=redirect_url, status_code=302)


def _mask_key(key: Optional[str]) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _sanitize_extra_config(extra: Optional[dict], integration_type: str) -> dict:
    """Remove sensitive tokens from extra_config before returning to client."""
    if not extra:
        return {}
    import json as _json
    if isinstance(extra, str):
        try:
            extra = _json.loads(extra)
        except Exception:
            extra = {}
    out = {k: v for k, v in (extra or {}).items() if k not in ("access_token", "refresh_token")}
    if (
        integration_type in GOOGLE_OAUTH_INTEGRATION_TYPES
        and ("access_token" in extra or "refresh_token" in extra)
    ):
        out["oauth_connected"] = True
    return out


class IntegrationUpdate(BaseModel):
    api_key: Optional[str] = Field(None, description="API key (stored as-is; encryption TODO)")
    extra_config: Optional[dict] = None
    client_slug: Optional[str] = None


@router.get("")
async def list_integrations(
    client_slug: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List integrations for the current user. If client_slug given, filter to that client; else agency-level (client_slug IS NULL)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if client_slug:
            rows = await conn.fetch(
                """
                SELECT integration_id, user_id, client_slug, integration_type, api_key_encrypted, extra_config, updated_at
                FROM client_integrations
                WHERE user_id = $1 AND client_slug = $2 AND integration_type IS NOT NULL
                ORDER BY integration_type
                """,
                current_user.user_id,
                client_slug,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT integration_id, user_id, client_slug, integration_type, api_key_encrypted, extra_config, updated_at
                FROM client_integrations
                WHERE user_id = $1 AND client_slug IS NULL AND integration_type IS NOT NULL
                ORDER BY integration_type
                """,
                current_user.user_id,
            )
    out = []
    for r in rows:
        extra = r["extra_config"]
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception:
                extra = {}
        out.append({
            "id": str(r.get("integration_id") or r.get("id", "")),
            "integration_type": r["integration_type"],
            "api_key_masked": _mask_key(r["api_key_encrypted"]),
            "extra_config": _sanitize_extra_config(extra, r["integration_type"]),
            "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
            "updated_at": r.get("updated_at").isoformat() if r.get("updated_at") else None,
        })
    return out


@router.get("/{integration_type}")
async def get_integration(
    integration_type: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get one integration by type."""
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT integration_id, integration_type, api_key_encrypted, extra_config, updated_at
            FROM client_integrations
            WHERE user_id = $1 AND integration_type = $2
            """,
            current_user.user_id,
            integration_type,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Integration not found")
    extra = row["extra_config"]
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except Exception:
            extra = {}
    return {
        "id": str(row.get("integration_id") or row.get("id", "")),
        "integration_type": row["integration_type"],
        "api_key_masked": _mask_key(row["api_key_encrypted"]),
        "extra_config": _sanitize_extra_config(extra, row["integration_type"]),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
    }


@router.put("/{integration_type}")
async def upsert_integration(
    integration_type: str,
    body: IntegrationUpdate,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Create or update integration for the current user. Optionally scoped to client_slug."""
    client_slug = body.client_slug if body.client_slug else None
    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT api_key_encrypted, extra_config FROM client_integrations
            WHERE user_id = $1 AND (client_slug IS NOT DISTINCT FROM $2) AND integration_type = $3
            """,
            current_user.user_id,
            client_slug,
            integration_type,
        )
        api_key = body.api_key if body.api_key else (existing["api_key_encrypted"] if existing else None)
        if body.extra_config is not None:
            extra_config = body.extra_config
        elif existing:
            extra = existing["extra_config"]
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except Exception:
                    extra = {}
            extra_config = extra or {}
        else:
            extra_config = {}
        extra_config_json = json.dumps(extra_config) if isinstance(extra_config, dict) else extra_config
        if existing:
            await conn.execute(
                """
                UPDATE client_integrations
                SET api_key_encrypted = $4, extra_config = $5, updated_at = now()
                WHERE user_id = $1 AND (client_slug IS NOT DISTINCT FROM $2) AND integration_type = $3
                """,
                current_user.user_id,
                client_slug,
                integration_type,
                api_key,
                extra_config_json,
            )
        else:
            integration_id = (
                f"int:{current_user.user_id}:{client_slug}:{integration_type}"
                if client_slug
                else f"int:{current_user.user_id}:{integration_type}"
            )
            await conn.execute(
                """
                INSERT INTO client_integrations
                    (integration_id, user_id, client_slug, integration_type, api_key_encrypted, extra_config, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, now())
                """,
                integration_id,
                current_user.user_id,
                client_slug,
                integration_type,
                api_key,
                extra_config_json,
            )
    return {"status": "ok", "integration_type": integration_type}


@router.delete("/{integration_type}")
async def delete_integration(
    integration_type: str,
    client_slug: Optional[str] = Query(None, description="Client slug for client-scoped disconnect"),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Delete integration for the current user. Optionally scoped to client_slug. Clears platform config for this client when present."""
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM client_integrations
            WHERE user_id = $1 AND (client_slug IS NOT DISTINCT FROM $2) AND integration_type = $3
            """,
            current_user.user_id,
            client_slug,
            integration_type,
        )
        if client_slug and result != "DELETE 0":
            platform = integration_type
            await conn.execute(
                """
                DELETE FROM client_platform_configs
                WHERE user_id = $1 AND client_slug = $2 AND platform = $3
                """,
                current_user.user_id,
                client_slug,
                platform,
            )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"status": "ok", "integration_type": integration_type}
