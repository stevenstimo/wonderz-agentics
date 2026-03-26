"""
Credential resolver — platform-owned client integrations first, then user-owned.

Lookup order:
1) client_slug + integration_type + owned_by = platform + usable credentials
2) user-owned row for (user_id, client_slug, integration_type)
3) None if nothing usable
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

# Rows usable for API calls (OAuth refresh or short-lived access)
_ACTIVE_SQL = """
  (
    COALESCE(is_active, false) = true
    OR extra_config->>'oauth_connected' = 'true'
    OR extra_config ? 'refresh_token'
    OR (NULLIF(TRIM(COALESCE(api_key_encrypted, '')), '') IS NOT NULL)
  )
"""


async def resolve_integration_row(
    conn: asyncpg.Connection,
    *,
    client_slug: str,
    integration_type: str,
    user_id: Optional[str] = None,
) -> Optional[asyncpg.Record]:
    """
    Return one client_integrations row for token refresh / extra_config reads.
    Platform-owned first, then user-owned for user_id.
    """
    if not client_slug or not integration_type:
        return None

    row = await conn.fetchrow(
        f"""
        SELECT integration_id, extra_config, api_key_encrypted, user_id, owned_by,
               integration_type, client_slug
        FROM client_integrations
        WHERE client_slug = $1
          AND integration_type = $2
          AND owned_by = 'platform'
          AND {_ACTIVE_SQL}
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 1
        """,
        client_slug,
        integration_type,
    )
    if row:
        logger.info(
            "credential_resolver: platform-owned row=%s client=%s integration=%s",
            row.get("integration_id"),
            client_slug,
            integration_type,
        )
        return row

    if user_id:
        row = await conn.fetchrow(
            f"""
            SELECT integration_id, extra_config, api_key_encrypted, user_id, owned_by,
                   integration_type, client_slug
            FROM client_integrations
            WHERE client_slug = $1
              AND integration_type = $2
              AND user_id = $3::uuid
              AND owned_by = 'user'
              AND {_ACTIVE_SQL}
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 1
            """,
            client_slug,
            integration_type,
            user_id,
        )
        if row:
            logger.info(
                "credential_resolver: user-owned row=%s client=%s integration=%s user=%s",
                row.get("integration_id"),
                client_slug,
                integration_type,
                user_id,
            )
            return row

    logger.info(
        "credential_resolver: geen credentials client=%s integration=%s",
        client_slug,
        integration_type,
    )
    return None


async def get_credentials(
    db: asyncpg.Connection,
    client_slug: str,
    integration_type: str,
    user_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Return client_integrations row as dict, or None."""
    row = await resolve_integration_row(
        db, client_slug=client_slug, integration_type=integration_type, user_id=user_id
    )
    return dict(row) if row else None


async def get_all_active_integrations(
    db: asyncpg.Connection,
    client_slug: str,
    user_id: Optional[str] = None,
) -> dict[str, dict[str, Any]]:
    """
    All integration types for a client with platform-first per type.
    Keys: integration_type (DB value).
    """
    result: dict[str, dict[str, Any]] = {}

    rows = await db.fetch(
        f"""
        SELECT DISTINCT ON (integration_type)
               integration_id, extra_config, api_key_encrypted, user_id, owned_by,
               integration_type, client_slug
        FROM client_integrations
        WHERE client_slug = $1
          AND owned_by = 'platform'
          AND {_ACTIVE_SQL}
        ORDER BY integration_type, updated_at DESC NULLS LAST
        """,
        client_slug,
    )
    for row in rows:
        it = row.get("integration_type")
        if it:
            result[str(it)] = dict(row)

    if user_id:
        rows_u = await db.fetch(
            f"""
            SELECT DISTINCT ON (integration_type)
                   integration_id, extra_config, api_key_encrypted, user_id, owned_by,
                   integration_type, client_slug
            FROM client_integrations
            WHERE client_slug = $1
              AND user_id = $2::uuid
              AND owned_by = 'user'
              AND {_ACTIVE_SQL}
            ORDER BY integration_type, updated_at DESC NULLS LAST
            """,
            client_slug,
            user_id,
        )
        for row in rows_u:
            it = row.get("integration_type")
            if it and str(it) not in result:
                result[str(it)] = dict(row)

    logger.info(
        "credential_resolver: %d integrations voor client=%s: %s",
        len(result),
        client_slug,
        list(result.keys()),
    )
    return result


async def mark_as_platform_owned(
    db: asyncpg.Connection,
    client_slug: str,
    integration_type: str,
    user_id: Optional[str] = None,
) -> bool:
    """
    Promote one user-owned integration to platform-owned.
    If user_id is set, only that row; otherwise the most recently updated matching row.
    """
    if user_id:
        status = await db.execute(
            f"""
            UPDATE client_integrations
            SET owned_by = 'platform', updated_at = now()
            WHERE client_slug = $1
              AND integration_type = $2
              AND user_id = $3::uuid
              AND owned_by = 'user'
              AND {_ACTIVE_SQL}
            """,
            client_slug,
            integration_type,
            user_id,
        )
    else:
        status = await db.execute(
            f"""
            UPDATE client_integrations
            SET owned_by = 'platform', updated_at = now()
            WHERE integration_id = (
              SELECT integration_id FROM client_integrations
              WHERE client_slug = $1
                AND integration_type = $2
                AND owned_by = 'user'
                AND {_ACTIVE_SQL}
              ORDER BY updated_at DESC NULLS LAST
              LIMIT 1
            )
            """,
            client_slug,
            integration_type,
        )
    try:
        n = int(str(status).split()[-1])
    except (ValueError, IndexError):
        n = 0
    logger.info(
        "credential_resolver: promoted %s rows naar platform client=%s integration=%s",
        n,
        client_slug,
        integration_type,
    )
    return n > 0
