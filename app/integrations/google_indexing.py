"""
Google Indexing API adapter.
Meldt URL's aan voor Google-indexering via Service Account.
Activeren: zet GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON in systemd override (base64-encoded JSON).

Base64-decode en JSON-parse gebeuren alleen in _get_service_account_credentials() bij gebruik,
niet bij module-import — ongeldige env-waarde crasht import niet.
"""
import base64
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_raw = os.getenv("GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON", "")
ENABLED = bool(_raw)

INDEXING_URL = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPES = ["https://www.googleapis.com/auth/indexing"]


def _get_service_account_credentials() -> dict | None:
    if not _raw:
        return None
    try:
        decoded = base64.b64decode(_raw).decode("utf-8")
        return json.loads(decoded)
    except Exception as e:
        logger.error("Indexing API: kan service account JSON niet parsen: %s", e)
        return None


async def _get_access_token(credentials: dict) -> str | None:
    """Haalt een access token op via JWT voor het service account."""
    try:
        import time

        import jwt

        now = int(time.time())
        payload = {
            "iss": credentials["client_email"],
            "scope": " ".join(SCOPES),
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }
        private_key = credentials["private_key"]
        token = jwt.encode(payload, private_key, algorithm="RS256")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": token,
                },
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
    except Exception as e:
        logger.error("Indexing API: access token fout: %s", e)
        return None


async def request_indexing(url: str, notification_type: str = "URL_UPDATED") -> dict:
    """
    Meldt een URL aan voor Google-indexering.
    notification_type: 'URL_UPDATED' of 'URL_DELETED'
    """
    if not ENABLED:
        return {"enabled": False, "data": None}

    credentials = _get_service_account_credentials()
    if not credentials:
        return {"enabled": True, "data": None, "error": "invalid_credentials"}

    access_token = await _get_access_token(credentials)
    if not access_token:
        return {"enabled": True, "data": None, "error": "token_error"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                INDEXING_URL,
                json={"url": url, "type": notification_type},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

        return {
            "enabled": True,
            "data": {
                "url": url,
                "type": notification_type,
                "notify_time": raw.get("urlNotificationMetadata", {})
                .get("latestUpdate", {})
                .get("notifyTime"),
            },
        }
    except Exception as e:
        logger.error("Indexing API fout voor %s: %s", url, e)
        return {"enabled": True, "data": None, "error": str(e)}
