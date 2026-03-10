"""
Auth middleware: Supabase JWT validation and role-based access.

- get_current_user: validates Bearer JWT, returns user_id + role from user_roles
- require_super_admin: raises 403 if role != 'super_admin'
"""

import logging
import os
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import get_db

logger = logging.getLogger(__name__)

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPER_ADMIN_EMAIL = "stevenstimo@gmail.com"

http_bearer = HTTPBearer(auto_error=False)


class TokenPayload:
    """Decoded JWT payload with user_id and role."""

    def __init__(self, user_id: str, role: str, email: str | None = None):
        self.user_id = user_id
        self.role = role
        self.email = email or ""


async def _get_current_user_impl(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> TokenPayload:
    """Validate Supabase Bearer JWT and return user_id + role."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Unauthorized: Bearer token required")

    token = credentials.credentials

    if not SUPABASE_JWT_SECRET:
        logger.warning("SUPABASE_JWT_SECRET not configured - auth will fail")
        raise HTTPException(status_code=503, detail="Auth not configured")

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.debug(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    email = (payload.get("email") or "").lower().strip()
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    try:
        user_id = str(UUID(sub))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token: invalid user_id")

    # Role from user_roles table; fallback to email check for super_admin
    role = "member"
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT role FROM user_roles WHERE user_id = $1",
                user_id,
            )
            if row:
                role = str(row["role"]).lower()
    except Exception as e:
        logger.warning(f"Could not fetch role for user {user_id}: {e}")
        if email == SUPER_ADMIN_EMAIL:
            role = "super_admin"

    if email == SUPER_ADMIN_EMAIL and role != "super_admin":
        role = "super_admin"

    return TokenPayload(user_id=user_id, role=role, email=email)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> TokenPayload:
    """FastAPI dependency: returns user_id and role. Raises 401 if not authenticated."""
    return await _get_current_user_impl(request, credentials)


async def require_super_admin(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> TokenPayload:
    """FastAPI dependency: same as get_current_user but raises 403 if role != super_admin."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: super_admin role required",
        )
    return current_user
