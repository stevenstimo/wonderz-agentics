"""Settings API routes.

GET/POST for the settings table (API keys, Supabase config).
Only super_admin (stevenstimo@gmail.com) can read/write.
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

import app.db as _db

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
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth[7:]
    # Decode JWT to get email (Supabase JWTs are standard)
    try:
        import json, base64
        payload = token.split(".")[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        email = data.get("email", "").lower()
        if email != SUPER_ADMIN_EMAIL:
            raise HTTPException(status_code=403, detail="Only super admin can access settings")
    except (IndexError, ValueError, Exception) as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=401, detail="Invalid token")


class SettingsUpdate(BaseModel):
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None


@router.get("/api/settings")
async def get_settings(request: Request):
    await _check_admin(request)

    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")
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

    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")
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
