"""
CredentialStore: Centraal toegangspunt voor credential encryptie/decryptie.

Nooit credentials direct uit DB lezen — altijd via deze class.
Credentials worden encrypted opgeslagen in agency_client_integrations.credentials (BYTEA).
"""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


class IntegrationNotFound(Exception):
    """Raised when no integration exists for client_id + platform."""

    pass


class CredentialStore:
    """
    Centraal toegangspunt voor credential encryptie/decryptie.
    Nooit credentials direct uit DB lezen — altijd via deze class.
    """

    def __init__(self, pool=None):
        self._pool = pool

    async def _get_pool(self):
        if self._pool:
            return self._pool
        from app.db import init_db_pool
        return await init_db_pool()

    def _get_key(self) -> str:
        key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
        if not key or len(key) < 32:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY must be set in environment (min 32 chars)"
            )
        return key

    async def get(self, client_id: str, platform: str) -> Dict[str, Any]:
        """
        Haal decrypted credentials op voor client_id + platform.
        Raises IntegrationNotFound als geen connected integratie.
        """
        pool = await self._get_pool()
        if not pool:
            raise IntegrationNotFound(f"No DB pool for {client_id}/{platform}")

        key = self._get_key()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT integration_id, credentials
                FROM client_integrations
                WHERE client_id = $1 AND platform = $2 AND status != 'disconnected'
                """,
                client_id,
                platform,
            )
            if not row or not row["credentials"]:
                raise IntegrationNotFound(f"No integration for {client_id}/{platform}")

            try:
                decrypted = await conn.fetchval(
                    "SELECT pgp_sym_decrypt($1::bytea, $2)",
                    bytes(row["credentials"]),
                    key,
                )
                if not decrypted:
                    raise IntegrationNotFound(f"Decrypt failed for {client_id}/{platform}")
                return json.loads(decrypted.decode("utf-8"))
            except Exception as e:
                logger.error("CredentialStore.get decrypt failed: %s", e)
                raise IntegrationNotFound(f"Decrypt failed for {client_id}/{platform}") from e

    async def store(self, integration_id: str, credentials: Dict[str, Any]) -> None:
        """
        Encrypt en sla credentials op voor integration_id.
        """
        pool = await self._get_pool()
        if not pool:
            raise RuntimeError("No DB pool for CredentialStore.store")

        key = self._get_key()
        payload = json.dumps(credentials)
        async with pool.acquire() as conn:
            encrypted = await conn.fetchval(
                "SELECT pgp_sym_encrypt($1::text, $2)",
                payload,
                key,
            )
            await conn.execute(
                """
                UPDATE client_integrations
                SET credentials = $1, status = 'connected', error_message = NULL
                WHERE integration_id = $2
                """,
                encrypted,
                integration_id,
            )
