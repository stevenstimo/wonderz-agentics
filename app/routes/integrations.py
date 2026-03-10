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
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# Google OAuth scopes for GA4, Google Ads, GSC (one flow for all three)
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",  # GA4
    "https://www.googleapis.com/auth/adwords",  # Google Ads
    "https://www.googleapis.com/auth/webmasters.readonly",  # GSC
]
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_INTEGRATION_TYPES = ["ga4", "google_ads", "google_search_console"]


def _create_oauth_state(user_id: str, secret: str, return_to: Optional[str] = None) -> str:
    """Create signed state for CSRF protection. Expires in 10 min."""
    payload = {"user_id": user_id, "exp": int(time.time()) + 600}
    if return_to:
        payload["return_to"] = return_to
    payload = json.dumps(payload)
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(
        secret.encode() if isinstance(secret, str) else secret,
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def _verify_oauth_state(state: str, secret: str) -> tuple[Optional[str], Optional[str]]:
    """Verify state and return (user_id, return_to) or (None, None)."""
    try:
        parts = state.split(".")
        if len(parts) != 2:
            return (None, None)
        payload_b64, sig = parts
        pad = 4 - len(payload_b64) % 4
        if pad != 4:
            payload_b64 += "=" * pad
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
        if payload.get("exp", 0) < time.time():
            return (None, None)
        expected = hmac.new(
            secret.encode() if isinstance(secret, str) else secret,
            parts[0].encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return (None, None)
        return (payload.get("user_id"), payload.get("return_to"))
    except Exception as e:
        logger.warning(f"State verification failed: {e}")
        return (None, None)


class GoogleAuthUrlRequest(BaseModel):
    return_to: Optional[str] = None


@router.post("/google/auth-url")
async def google_auth_url(
    body: Optional[GoogleAuthUrlRequest] = Body(None),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Generate Google OAuth URL with GA4, Google Ads, GSC scopes. Redirect user to this URL."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured (GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI)",
        )
    secret = os.getenv("SUPABASE_JWT_SECRET", "fallback-secret-change-me")
    return_to = body.return_to if body and body.return_to else None
    state = _create_oauth_state(current_user.user_id, secret, return_to)
    scopes = " ".join(GOOGLE_OAUTH_SCOPES)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    qs = urlencode(params)
    url = f"{GOOGLE_AUTH_URL}?{qs}"
    return {"url": url}


@router.get("/google/callback")
async def google_oauth_callback(code: Optional[str] = None, state: Optional[str] = None):
    """OAuth callback from Google. Exchange code for tokens, store for ga4/google_ads/gsc, redirect to /integrations."""
    frontend_base = os.getenv("FRONTEND_BASE_URL", "https://wonderz-agentic.exe.xyz")
    integrations_url = f"{frontend_base.rstrip('/')}/integrations"

    if not code or not state:
        logger.warning("Google callback missing code or state")
        return RedirectResponse(url=f"{integrations_url}?error=missing_params", status_code=302)

    secret = os.getenv("SUPABASE_JWT_SECRET", "fallback-secret-change-me")
    user_id, return_to = _verify_oauth_state(state, secret)
    if not user_id:
        logger.warning("Google callback invalid state")
        return RedirectResponse(url=f"{integrations_url}?error=invalid_state", status_code=302)

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        logger.error("Google OAuth not configured")
        return RedirectResponse(url=f"{integrations_url}?error=config", status_code=302)

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
        return RedirectResponse(url=f"{integrations_url}?error=token_exchange", status_code=302)

    data = resp.json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        logger.warning("Google did not return refresh_token (try prompt=consent)")
    # Store refresh_token as main credential; use it for all three integration types
    token_to_store = refresh_token or access_token
    if not token_to_store:
        return RedirectResponse(url=f"{integrations_url}?error=no_tokens", status_code=302)

    extra_config = {"access_token": access_token}
    if refresh_token:
        extra_config["refresh_token"] = refresh_token

    pool = await get_db()
    async with pool.acquire() as conn:
        for integration_type in GOOGLE_INTEGRATION_TYPES:
            integration_id = f"int:{user_id}:{integration_type}"
            await conn.execute(
                """
                INSERT INTO client_integrations
                    (integration_id, user_id, integration_type, api_key_encrypted, extra_config, updated_at)
                VALUES ($1, $2, $3, $4, $5, now())
                ON CONFLICT (user_id, integration_type) DO UPDATE SET
                    api_key_encrypted = EXCLUDED.api_key_encrypted,
                    extra_config = EXCLUDED.extra_config,
                    updated_at = now()
                """,
                integration_id,
                user_id,
                integration_type,
                token_to_store,
                json.dumps(extra_config),
            )

    if return_to:
        redirect_url = f"{frontend_base.rstrip('/')}{return_to}?connected=google"
    else:
        redirect_url = f"{integrations_url}?connected=google"
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
    out = {k: v for k, v in (extra or {}).items() if k not in ("access_token", "refresh_token")}
    if integration_type in GOOGLE_INTEGRATION_TYPES and ("access_token" in extra or "refresh_token" in extra):
        out["oauth_connected"] = True
    return out


class IntegrationUpdate(BaseModel):
    api_key: Optional[str] = Field(None, description="API key (stored as-is; encryption TODO)")
    extra_config: Optional[dict] = None


@router.get("")
async def list_integrations(current_user: TokenPayload = Depends(get_current_user)):
    """List integrations for the current user."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT integration_id, user_id, integration_type, api_key_encrypted, extra_config, updated_at
            FROM client_integrations
            WHERE user_id = $1 AND integration_type IS NOT NULL
            ORDER BY integration_type
            """,
            current_user.user_id,
        )
    return [
        {
            "id": str(r.get("integration_id") or r.get("id", "")),
            "integration_type": r["integration_type"],
            "api_key_masked": _mask_key(r["api_key_encrypted"]),
            "extra_config": _sanitize_extra_config(r["extra_config"], r["integration_type"]),
            "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
            "updated_at": r.get("updated_at").isoformat() if r.get("updated_at") else None,
        }
        for r in rows
    ]


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
    return {
        "id": str(row.get("integration_id") or row.get("id", "")),
        "integration_type": row["integration_type"],
        "api_key_masked": _mask_key(row["api_key_encrypted"]),
        "extra_config": _sanitize_extra_config(row["extra_config"], row["integration_type"]),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
    }


@router.put("/{integration_type}")
async def upsert_integration(
    integration_type: str,
    body: IntegrationUpdate,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Create or update integration for the current user."""
    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT api_key_encrypted, extra_config FROM client_integrations WHERE user_id = $1 AND integration_type = $2",
            current_user.user_id,
            integration_type,
        )
        api_key = body.api_key if body.api_key else (existing["api_key_encrypted"] if existing else None)
        extra_config = body.extra_config if body.extra_config is not None else ((existing["extra_config"] or {}) if existing else {})
        if existing:
            await conn.execute(
                """
                UPDATE client_integrations
                SET api_key_encrypted = $3, extra_config = $4, updated_at = now()
                WHERE user_id = $1 AND integration_type = $2
                """,
                current_user.user_id,
                integration_type,
                api_key,
                extra_config,
            )
        else:
            integration_id = f"int:{current_user.user_id}:{integration_type}"
            await conn.execute(
                """
                INSERT INTO client_integrations
                    (integration_id, user_id, integration_type, api_key_encrypted, extra_config, updated_at)
                VALUES ($1, $2, $3, $4, $5, now())
                """,
                integration_id,
                current_user.user_id,
                integration_type,
                api_key,
                extra_config,
            )
    return {"status": "ok", "integration_type": integration_type}


@router.delete("/{integration_type}")
async def delete_integration(
    integration_type: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Delete integration for the current user."""
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM client_integrations WHERE user_id = $1 AND integration_type = $2",
            current_user.user_id,
            integration_type,
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"status": "ok", "integration_type": integration_type}
