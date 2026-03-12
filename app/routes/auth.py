"""Auth routes — OAuth callbacks (e.g. Meta) that redirect without requiring JWT."""

import datetime
import json
import logging
import os

import httpx
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/meta/callback")
async def meta_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """OAuth callback from Meta. Exchange code for tokens, store in client_integrations, redirect to frontend."""
    frontend_base = os.getenv("FRONTEND_BASE_URL", "https://wonderz-agentic.exe.xyz").rstrip("/")

    if error or not code or not state:
        return RedirectResponse(
            url=f"{frontend_base}/clients?meta_error=auth_failed",
            status_code=302,
        )

    try:
        client_slug = state.split(":")[0]
    except Exception:
        return RedirectResponse(
            url=f"{frontend_base}/clients?meta_error=invalid_state",
            status_code=302,
        )

    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")
    redirect_uri = os.getenv("META_REDIRECT_URI")

    if not app_id or not app_secret or not redirect_uri:
        logger.error("Meta OAuth not configured (META_APP_ID/SECRET/REDIRECT_URI)")
        return RedirectResponse(
            url=f"{frontend_base}/clients/{client_slug}/integrations?meta_error=config",
            status_code=302,
        )

    async with httpx.AsyncClient() as client:
        token_resp = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )

    if token_resp.status_code != 200:
        logger.warning("Meta token exchange failed: %s %s", token_resp.status_code, token_resp.text[:200])
        return RedirectResponse(
            url=f"{frontend_base}/clients/{client_slug}/integrations?meta_error=token_exchange",
            status_code=302,
        )

    tokens = token_resp.json()
    short_lived_token = tokens.get("access_token")
    if not short_lived_token:
        return RedirectResponse(
            url=f"{frontend_base}/clients/{client_slug}/integrations?meta_error=token_exchange",
            status_code=302,
        )

    async with httpx.AsyncClient() as client:
        ll_resp = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_lived_token,
            },
        )

    if ll_resp.status_code != 200:
        logger.warning("Meta long-lived token failed: %s %s", ll_resp.status_code, ll_resp.text[:200])
        return RedirectResponse(
            url=f"{frontend_base}/clients/{client_slug}/integrations?meta_error=token_exchange",
            status_code=302,
        )

    ll_tokens = ll_resp.json()
    long_lived_token = ll_tokens.get("access_token")
    expires_in = ll_tokens.get("expires_in", 5183944)
    expires_at = int((datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)).timestamp())

    async with httpx.AsyncClient() as client:
        me_resp = await client.get(
            "https://graph.facebook.com/v19.0/me",
            params={"fields": "id,name,email", "access_token": long_lived_token},
        )
    me = me_resp.json() if me_resp.status_code == 200 else {}

    extra_config = json.dumps({
        "access_token": long_lived_token,
        "expires_at": expires_at,
        "oauth_connected": True,
        "meta_user_id": me.get("id"),
        "meta_user_name": me.get("name"),
    })

    pool = await get_db()
    async with pool.acquire() as conn:
        client_row = await conn.fetchrow(
            "SELECT user_id FROM clients WHERE slug = $1",
            client_slug,
        )
        if not client_row:
            return RedirectResponse(
                url=f"{frontend_base}/clients?meta_error=client_not_found",
                status_code=302,
            )

        user_id = str(client_row["user_id"])
        integration_id = f"int:{user_id}:{client_slug}:meta_ads"

        await conn.execute(
            """
            INSERT INTO client_integrations
                (integration_id, user_id, client_slug, integration_type,
                 api_key_encrypted, extra_config, updated_at)
            VALUES
                ($1, $2, $3, 'meta_ads', '', $4::jsonb, now())
            ON CONFLICT (user_id, client_slug, integration_type)
            DO UPDATE SET
                extra_config = EXCLUDED.extra_config,
                updated_at = now()
            """,
            integration_id,
            user_id,
            client_slug,
            extra_config,
        )

    return RedirectResponse(
        url=f"{frontend_base}/clients/{client_slug}/integrations?connected=meta_ads",
        status_code=302,
    )
