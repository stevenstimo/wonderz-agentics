"""Clients API — client management and platform configs.

Uses clients.slug as identifier. client_platform_configs stores platform-specific IDs per client.
"""

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import get_db
from app.middleware.auth import TokenPayload, get_current_user

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
