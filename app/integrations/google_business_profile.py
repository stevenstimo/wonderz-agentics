"""
Google Business Profile API adapter (voorheen Google My Business).
Reviews, insights en locatiedata per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth). Geen platform-level env var nodig.
"""
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://mybusinessaccountmanagement.googleapis.com/v1"
BUSINESS_INFO_URL = "https://mybusinessinformation.googleapis.com/v1"


async def get_locations(access_token: str) -> dict:
    """Haalt alle Business Profile locaties op voor dit account."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/accounts",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            accounts = resp.json().get("accounts", [])
            if not accounts:
                return {"enabled": True, "data": [], "error": "no_accounts"}

            account_name = accounts[0]["name"]

            resp2 = await client.get(
                f"{BUSINESS_INFO_URL}/{account_name}/locations",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp2.raise_for_status()
            locations = resp2.json().get("locations", [])

        return {
            "enabled": True,
            "data": {
                "account": account_name,
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


async def get_reviews(access_token: str, location_name: str) -> dict:
    """Haalt reviews op voor een specifieke locatie."""
    try:
        reviews_url = "https://mybusiness.googleapis.com/v4"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{reviews_url}/{location_name}/reviews",
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
                        "reviewer": r.get("reviewer", {}).get("displayName"),
                    }
                    for r in reviews[:20]
                ],
            },
        }
    except Exception as e:
        logger.error("Business Profile reviews fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}
