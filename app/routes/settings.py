"""Settings API routes.

GET/POST for the settings table (API keys, Supabase config).
Only super_admin (stevenstimo@gmail.com) can read/write.
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

SUPER_ADMIN_EMAIL = "stevenstimo@gmail.com"


def _mask_key(key: Optional[str]) -> str:
    """Return masked version of a key for display."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


async def _check_admin(request: Request):
    """Check if the request comes from super admin via Supabase JWT."""
    import json, base64

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        logger.warning("Settings access: no Bearer token")
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth[7:]
    try:
        parts = token.split(".")
        if len(parts) < 2:
            raise ValueError("Malformed JWT")
        payload = parts[1]
        # Add padding for base64
        payload += "=" * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        email = (data.get("email") or "").lower().strip()
        logger.info(f"Settings access by: {email}")
        if email != SUPER_ADMIN_EMAIL:
            raise HTTPException(status_code=403, detail=f"Only super admin can access settings (got: {email or 'no email in token'})")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


class SettingsUpdate(BaseModel):
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None


@router.get("/api/settings")
async def get_settings(request: Request):
    await _check_admin(request)

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM settings WHERE id = 'default'")

    if not row:
        return {
            "gemini_api_key": "",
            "anthropic_api_key": "",
            "supabase_url": "",
            "supabase_key": "",
        }

    return {
        "gemini_api_key": row["gemini_api_key"] or "",
        "anthropic_api_key": row["anthropic_api_key"] or "",
        "supabase_url": row["supabase_url"] or "",
        "supabase_key": row["supabase_key"] or "",
    }


@router.post("/api/settings")
async def save_settings(request: Request, body: SettingsUpdate):
    await _check_admin(request)

    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM settings WHERE id = 'default'")

        if existing:
            await conn.execute(
                """UPDATE settings
                   SET gemini_api_key = $1,
                       anthropic_api_key = $2,
                       supabase_url = $3,
                       supabase_key = $4,
                       updated_at = NOW()
                   WHERE id = 'default'""",
                body.gemini_api_key or "",
                body.anthropic_api_key or "",
                body.supabase_url or "",
                body.supabase_key or "",
            )
        else:
            await conn.execute(
                """INSERT INTO settings (id, gemini_api_key, anthropic_api_key, supabase_url, supabase_key, updated_at)
                   VALUES ('default', $1, $2, $3, $4, NOW())""",
                body.gemini_api_key or "",
                body.anthropic_api_key or "",
                body.supabase_url or "",
                body.supabase_key or "",
            )

    return {"status": "ok", "message": "Settings saved"}
