"""
Google Business Profile API adapter (voorheen Google My Business).
Reviews, insights en locatiedata per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_ACCOUNT_MGMT = "https://mybusinessaccountmanagement.googleapis.com/v1"
BUSINESS_INFO_URL = "https://mybusinessbusinessinformation.googleapis.com/v1"
REVIEWS_BASE = "https://mybusiness.googleapis.com/v4"


def _account_name(account_id: str) -> str:
    s = str(account_id).strip()
    return s if s.startswith("accounts/") else f"accounts/{s}"


def _location_resource(account_id: str, location_id: str) -> str:
    """Full resource name: accounts/{id}/locations/{id}."""
    acct = _account_name(account_id)
    loc = str(location_id).strip()
    if loc.startswith(acct + "/"):
        return loc
    if loc.startswith("accounts/") and "/locations/" in loc:
        return loc
    suffix = loc.split("locations/")[-1] if "locations/" in loc else loc
    return f"{acct}/locations/{suffix}"


async def get_accounts(access_token: str) -> dict:
    """Haal Business Profile accounts op."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_ACCOUNT_MGMT}/accounts",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()
        accounts = raw.get("accounts", [])
        return {
            "enabled": True,
            "data": {
                "accounts": [
                    {
                        "name": a.get("name"),
                        "account_name": a.get("accountName"),
                        "type": a.get("type"),
                    }
                    for a in accounts
                ]
            },
        }
    except Exception as e:
        logger.error("Business Profile accounts fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def get_locations(access_token: str, account_id: str) -> dict:
    """Haal locaties op voor een account (account_id: accounts/123 of 123)."""
    try:
        name = _account_name(account_id)
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BUSINESS_INFO_URL}/{name}/locations",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            locations = resp.json().get("locations", [])
        return {
            "enabled": True,
            "data": {
                "account": name,
                "locations": [
                    {
                        "name": loc.get("name"),
                        "title": loc.get("title"),
                        "store_code": loc.get("storeCode"),
                    }
                    for loc in locations
                ],
            },
        }
    except Exception as e:
        logger.error("Business Profile locations fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def get_reviews(access_token: str, account_id: str, location_id: str) -> dict:
    """Haal reviews op voor een locatie (location_id: resource suffix of volledig pad)."""
    loc_name = _location_resource(account_id, location_id)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{REVIEWS_BASE}/{loc_name}/reviews",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()
        reviews = raw.get("reviews", [])
        return {
            "enabled": True,
            "data": {
                "average_rating": raw.get("averageRating"),
                "total_review_count": raw.get("totalReviewCount"),
                "reviews": [
                    {
                        "rating": r.get("starRating"),
                        "comment": r.get("comment", ""),
                        "create_time": r.get("createTime"),
                        "reviewer": (r.get("reviewer") or {}).get("displayName"),
                    }
                    for r in reviews[:20]
                ],
            },
        }
    except Exception as e:
        logger.error("Business Profile reviews fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


class GoogleBusinessProfileAdapter:
    """Registry entry + callable surface for Business Profile."""

    get_accounts = staticmethod(get_accounts)
    get_locations = staticmethod(get_locations)
    get_reviews = staticmethod(get_reviews)
