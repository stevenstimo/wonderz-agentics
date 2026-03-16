"""
User management routes: invite, list, delete. Super admin only.
Uses Supabase Admin API for auth (invite/delete) and app DB for user_roles.
"""
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from app.database import get_db
from app.middleware.auth import require_super_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


def get_supabase_admin():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not service_key:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set",
        )
    return create_client(url, service_key)


@router.post("/invite")
async def invite_user(
    body: dict,
    current_user=Depends(require_super_admin),
    pool=Depends(get_db),
) -> dict[str, Any]:
    email = (body.get("email") or "").strip()
    role = (body.get("role") or "user").strip().lower()

    if not email:
        raise HTTPException(status_code=400, detail="email is verplicht")

    if role not in ("super_admin", "admin", "user"):
        raise HTTPException(status_code=400, detail="Ongeldige rol")

    supabase_admin = get_supabase_admin()

    try:
        response = supabase_admin.auth.admin.invite_user_by_email(email)
        invited_user_id = str(response.user.id)
    except Exception as e:
        logger.warning("Invite failed for %s: %s", email, e)
        raise HTTPException(status_code=400, detail=f"Uitnodiging mislukt: {str(e)}") from e

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_roles (user_id, role)
            VALUES ($1::uuid, $2)
            ON CONFLICT (user_id) DO UPDATE SET role = $2
            """,
            invited_user_id,
            role,
        )

    return {"success": True, "email": email, "role": role, "user_id": invited_user_id}


@router.get("/")
async def list_users(
    current_user=Depends(require_super_admin),
    pool=Depends(get_db),
) -> dict[str, Any]:
    supabase_admin = get_supabase_admin()
    response = supabase_admin.auth.admin.list_users()
    # list_users returns a list of User (or object with .users in some versions)
    auth_users_list = response if isinstance(response, list) else (getattr(response, "users", None) or [])
    auth_users = {str(u.id): u for u in auth_users_list}

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, role FROM user_roles")
        role_map = {str(r["user_id"]): r["role"] for r in rows}

    users = []
    for uid, user in auth_users.items():
        users.append({
            "user_id": uid,
            "email": getattr(user, "email", None) or "",
            "role": role_map.get(uid, "user"),
            "created_at": getattr(user, "created_at", None),
            "last_sign_in_at": getattr(user, "last_sign_in_at", None),
        })

    users.sort(key=lambda u: (u["created_at"] or ""), reverse=True)
    return {"users": users, "count": len(users)}


@router.delete("/{user_id}")
async def remove_user(
    user_id: str,
    current_user=Depends(require_super_admin),
    pool=Depends(get_db),
) -> dict[str, Any]:
    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Je kunt jezelf niet verwijderen")

    supabase_admin = get_supabase_admin()
    try:
        supabase_admin.auth.admin.delete_user(user_id)
    except Exception as e:
        logger.warning("Delete user %s failed: %s", user_id, e)
        raise HTTPException(status_code=400, detail=f"Verwijderen mislukt: {str(e)}") from e

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM user_roles WHERE user_id = $1::uuid", user_id)

    return {"success": True, "user_id": user_id}


VALID_ROLES = ("super_admin", "admin", "user")


@router.get("/permissions")
async def get_permissions(
    current_user=Depends(require_super_admin),
    pool=Depends(get_db),
) -> dict[str, Any]:
    """Return matrix role -> permission -> enabled. Super admin only (for UI)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, permission, enabled FROM role_permissions ORDER BY role, permission"
        )
    permissions: dict[str, dict[str, bool]] = {}
    for r in rows:
        role_name = str(r["role"])
        if role_name not in permissions:
            permissions[role_name] = {}
        permissions[role_name][str(r["permission"])] = bool(r["enabled"])
    return {"permissions": permissions}


@router.put("/permissions")
async def update_permission(
    body: dict,
    current_user=Depends(require_super_admin),
    pool=Depends(get_db),
) -> dict[str, Any]:
    """Set one permission for a role. Super admin only."""
    role = (body.get("role") or "").strip().lower()
    permission = (body.get("permission") or "").strip()
    enabled = body.get("enabled", False)

    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Ongeldige rol")
    if not permission:
        raise HTTPException(status_code=400, detail="permission is verplicht")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO role_permissions (role, permission, enabled)
            VALUES ($1, $2, $3)
            ON CONFLICT (role, permission) DO UPDATE SET enabled = $3
            """,
            role,
            permission,
            enabled,
        )
    return {"success": True, "role": role, "permission": permission, "enabled": enabled}
