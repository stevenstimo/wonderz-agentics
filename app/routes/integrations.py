"""Integrations API — per-user API keys and credentials.

Uses get_current_user for user_id from JWT. integration_type from path (e.g. klaviyo).
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _mask_key(key: Optional[str]) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


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
            "extra_config": r["extra_config"] or {},
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
        "extra_config": row["extra_config"] or {},
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
            integration_id = str(uuid.uuid4())
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
