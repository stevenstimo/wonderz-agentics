"""
Auth middleware: Supabase JWT validation and role-based access.

Supabase uses ES256 (asymmetric) JWTs. We validate via the JWKS endpoint
and cache keys to avoid HTTP calls per request.

- get_current_user: validates Bearer JWT, returns user_id + role from user_roles
- require_super_admin: raises 403 if role != 'super_admin'
"""

import logging
import os
from typing import Annotated
from uuid import UUID

import jwt
from jwt import PyJWKClient, PyJWKClientError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import get_db

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    "https://cqasccazioqjodctawzx.supabase.co",
).rstrip("/")
JWKS_URI = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
SUPER_ADMIN_EMAIL = "stevenstimo@gmail.com"

# PyJWKClient caches JWKS keys (default TTL 5 min); no HTTP call per request
_jwk_client: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient:
    """Lazy singleton for JWKS client with built-in key caching."""
    global _jwk_client
    if _jwk_client is None:
        _jwk_client = PyJWKClient(
            JWKS_URI,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=3600,  # 1 hour cache; Supabase key rotation is rare
        )
    return _jwk_client


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
    """Validate Supabase Bearer JWT (ES256 via JWKS) and return user_id + role."""
    if not credentials or not credentials.credentials:
        logger.warning("[auth] 401: Bearer token missing (no credentials or empty)")
        raise HTTPException(status_code=401, detail="Unauthorized: Bearer token required")

    token = credentials.credentials

    if not SUPABASE_URL:
        logger.warning("SUPABASE_URL not configured - auth will fail")
        raise HTTPException(status_code=503, detail="Auth not configured")

    try:
        jwk_client = _get_jwk_client()
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except PyJWKClientError as e:
        logger.warning(f"[auth] JWKS error: {e}")
        raise HTTPException(status_code=503, detail="Auth service unavailable")
    except jwt.ExpiredSignatureError as e:
        logger.warning(f"[auth] 401: Token expired - {e}")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"[auth] 401: Invalid token - {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    email = (payload.get("email") or "").lower().strip()
    if not sub:
        logger.warning("[auth] 401: Invalid token - missing sub claim")
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    try:
        user_id = str(UUID(sub))
    except ValueError:
        logger.warning(f"[auth] 401: Invalid token - invalid user_id (sub={sub!r})")
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
        logger.warning(
            f"[auth] 403: Forbidden - role={current_user.role!r} (email={current_user.email!r}), super_admin required"
        )
        raise HTTPException(
            status_code=403,
            detail="Forbidden: super_admin role required",
        )
    return current_user
