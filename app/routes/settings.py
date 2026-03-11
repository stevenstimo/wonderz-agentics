"""Settings API routes.

GET/POST for the settings table (API keys, Supabase config).
Only super_admin (stevenstimo@gmail.com) can read/write.
"""

import logging
import os
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

SUPER_ADMIN_EMAIL = "stevenstimo@gmail.com"

# Env vars the app needs — key -> (label, required, description)
ENV_VAR_SPEC = {
    "ANTHROPIC_API_KEY": ("Anthropic API Key", True, "Vereist voor Claude AI"),
    "GEMINI_API_KEY": ("Gemini API Key", False, "Optioneel voor Gemini AI"),
    "GOOGLE_CLIENT_ID": ("Google Client ID", True, "Vereist voor Google OAuth"),
    "GOOGLE_CLIENT_SECRET": ("Google Client Secret", True, "Vereist voor Google OAuth"),
    "GOOGLE_REDIRECT_URI": ("Google Redirect URI", True, "OAuth callback URL voor Google (bijv. https://wonderz-agentic.exe.xyz/api/integrations/google/callback)"),
    "GOOGLE_ADS_DEVELOPER_TOKEN": ("Google Ads Developer Token", True, "Vereist voor Google Ads campagne data"),
    "SUPABASE_URL": ("Supabase URL", True, "Vereist voor database en auth"),
    "SUPABASE_KEY": ("Supabase Key", True, "Vereist voor Supabase API"),
    "SUPABASE_JWT_SECRET": ("Supabase JWT Secret", True, "Vereist voor JWT verificatie"),
    "CREDENTIAL_ENCRYPTION_KEY": ("Credential Encryption Key", True, "Vereist voor encryptie van credentials"),
}

SYSTEMD_OVERRIDE_DIR = "/etc/systemd/system/wonderz-backend.service.d"
SYSTEMD_OVERRIDE_FILE = f"{SYSTEMD_OVERRIDE_DIR}/override.conf"


def _mask_key(key: Optional[str]) -> str:
    """Return masked version of a key for display."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _env_preview(value: Optional[str]) -> Optional[str]:
    """Preview: first 3 + ... + last 3 chars. Never return full value."""
    if not value or len(value) < 7:
        return None
    return value[:3] + "..." + value[-3:]


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


# --- Env vars (systemd override) ---


class EnvVarUpdate(BaseModel):
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


def _read_env_file() -> dict[str, str]:
    """Read .env and .env.vm from project root. .env.vm overrides .env."""
    root = Path(__file__).resolve().parent.parent
    merged: dict[str, str] = {}
    for name in (".env", ".env.vm"):
        path = root / name
        if path.exists():
            vals = dotenv_values(path)
            if vals:
                merged.update({k: str(v) for k, v in vals.items() if v is not None})
    return merged


def _get_merged_env_vars() -> dict[str, str]:
    """Merge env from systemd override and .env. .env overrides systemd (matches load_dotenv behavior)."""
    merged = _read_systemd_override()
    env_file = _read_env_file()
    merged.update(env_file)
    return merged


def _read_systemd_override() -> dict[str, str]:
    """Read current Environment vars from systemd override file."""
    result = subprocess.run(
        ["sudo", "cat", SYSTEMD_OVERRIDE_FILE],
        capture_output=True,
        text=True,
        timeout=5,
    )
    env_vars: dict[str, str] = {}
    if result.returncode != 0 or not result.stdout.strip():
        return env_vars
    in_service = False
    for line in result.stdout.splitlines():
        line = line.strip()
        if line == "[Service]":
            in_service = True
            continue
        if line.startswith("[") and line.endswith("]"):
            in_service = False
            continue
        if in_service and line.startswith("Environment="):
            # Match value that may contain escaped quotes
            match = re.match(r'Environment="((?:[^"\\]|\\.)*)"', line)
            if match:
                inner = match.group(1)
                eq = inner.find("=")
                if eq > 0:
                    k, v = inner[:eq], inner[eq + 1 :]
                    env_vars[k] = v.replace("\\\\", "\\").replace('\\"', '"')
    return env_vars


def _write_systemd_override(env_vars: dict[str, str]) -> None:
    """Write Environment vars to systemd override file."""
    subprocess.run(
        ["sudo", "mkdir", "-p", SYSTEMD_OVERRIDE_DIR],
        capture_output=True,
        check=True,
        timeout=5,
    )
    lines = ["[Service]\n"]
    for k, v in sorted(env_vars.items()):
        safe = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'Environment="{k}={safe}"\n')
    content = "".join(lines)
    proc = subprocess.run(
        ["sudo", "tee", SYSTEMD_OVERRIDE_FILE],
        input=content.encode(),
        capture_output=True,
        timeout=5,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to write override: {proc.stderr.decode()}")
    subprocess.run(
        ["sudo", "systemctl", "daemon-reload"],
        capture_output=True,
        check=True,
        timeout=10,
    )
    # Restart in background so we can return 200 before process dies
    subprocess.Popen(
        ["sudo", "systemctl", "restart", "wonderz-backend"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@router.get("/api/settings/env-vars")
async def get_env_vars(current_user: TokenPayload = Depends(get_current_user)):
    """Read from systemd override and .env, return which keys are configured. Preview: first 3 + ... + last 3."""

    merged = _get_merged_env_vars()
    out = []
    for key, (label, required, description) in ENV_VAR_SPEC.items():
        value = merged.get(key) or os.getenv(key)
        configured = bool(value)
        preview = _env_preview(value) if value else None
        out.append({
            "key": key,
            "label": label,
            "required": required,
            "configured": configured,
            "preview": preview,
            "description": description,
        })
    return out


@router.post("/api/settings/env-vars")
async def save_env_var(body: EnvVarUpdate, current_user: TokenPayload = Depends(get_current_user)):
    """Save env var to systemd override and reload/restart wonderz-backend."""

    if body.key not in ENV_VAR_SPEC:
        raise HTTPException(status_code=400, detail=f"Unknown key: {body.key}")

    try:
        env_vars = _read_systemd_override()
        env_vars[body.key] = body.value
        _write_systemd_override(env_vars)
    except Exception as e:
        logger.exception("Failed to save env var %s", body.key)
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "preview": _env_preview(body.value)}
