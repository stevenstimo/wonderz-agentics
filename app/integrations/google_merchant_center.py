"""
Google Merchant Center API (Content API for Shopping) adapter.
Productfeed, approve/reject statussen en feed-kwaliteit per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://shoppingcontent.googleapis.com/content/v2.1"


async def get_account_status(access_token: str, merchant_id: str) -> dict:
    """Haalt accountstatus en openstaande issues op."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{merchant_id}/accountstatuses/{merchant_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

        return {
            "enabled": True,
            "data": {
                "merchant_id": merchant_id,
                "account_level_issues": raw.get("accountLevelIssues", []),
                "products_pending_approval": raw.get("productsStats", {}).get("pendingApproval"),
                "products_disapproved": raw.get("productsStats", {}).get("disapproved"),
                "products_active": raw.get("productsStats", {}).get("active"),
            },
        }
    except Exception as e:
        logger.error("Merchant Center account status fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def get_product_statuses(access_token: str, merchant_id: str, max_results: int = 50) -> dict:
    """Haalt productstatus op: goedgekeurd, afgekeurd, reden."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{merchant_id}/productstatuses",
                params={"maxResults": max_results},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

        resources = raw.get("resources", [])
        return {
            "enabled": True,
            "data": {
                "total": raw.get("nextPageToken"),
                "products": [
                    {
                        "product_id": p.get("productId"),
                        "title": p.get("title"),
                        "status": "approved" if not p.get("itemLevelIssues") else "has_issues",
                        "issues": [
                            {
                                "code": issue.get("code"),
                                "servability": issue.get("servability"),
                                "description": issue.get("description"),
                            }
                            for issue in p.get("itemLevelIssues", [])
                        ],
                    }
                    for p in resources
                ],
            },
        }
    except Exception as e:
        logger.error("Merchant Center product statuses fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}
