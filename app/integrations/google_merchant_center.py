"""
Google Merchant Center API (Content API for Shopping) adapter.
Productfeed en accountstatus per klant via OAuth.
Activeren: klant koppelt via Integrations UI (OAuth).
"""
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://shoppingcontent.googleapis.com/content/v2.1"


async def get_accounts(access_token: str) -> dict:
    """Lijst Merchant Center / Content API accounts."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/accounts",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()
        resources = raw.get("items", []) or raw.get("resources", [])
        return {
            "enabled": True,
            "data": {
                "accounts": [
                    {
                        "id": str(a.get("id", "")),
                        "name": a.get("name"),
                        "website_url": a.get("websiteUrl"),
                    }
                    for a in resources
                ]
            },
        }
    except Exception as e:
        logger.error("Merchant Center accounts fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def get_products(access_token: str, merchant_id: str, max_results: int = 50) -> dict:
    """Productlijst voor een merchant ID."""
    try:
        mid = str(merchant_id).strip()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{mid}/products",
                params={"maxResults": max_results},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()
        resources = raw.get("resources", [])
        return {
            "enabled": True,
            "data": {
                "merchant_id": mid,
                "products": [
                    {
                        "id": p.get("id"),
                        "title": p.get("title"),
                        "content_language": p.get("contentLanguage"),
                        "target_country": p.get("targetCountry"),
                    }
                    for p in resources
                ],
            },
        }
    except Exception as e:
        logger.error("Merchant Center products fout: %s", e)
        return {"enabled": True, "data": None, "error": str(e)}


async def get_performance(
    access_token: str, merchant_id: str, start_date: str, end_date: str
) -> dict:
    """Lichte performance-snapshot (accountstatus + productstats; geen volledige Shopping reports)."""
    st = await get_account_status(access_token, merchant_id)
    if st.get("error") or not st.get("data"):
        return st
    return {
        "enabled": True,
        "data": {
            "merchant_id": str(merchant_id),
            "period": {"start": start_date, "end": end_date},
            "account_snapshot": st.get("data"),
        },
    }


async def get_account_status(access_token: str, merchant_id: str) -> dict:
    """Haalt accountstatus en openstaande issues op."""
    try:
        mid = str(merchant_id).strip()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{mid}/accountstatuses/{mid}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

        return {
            "enabled": True,
            "data": {
                "merchant_id": mid,
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
        mid = str(merchant_id).strip()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BASE_URL}/{mid}/productstatuses",
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


class GoogleMerchantCenterAdapter:
    get_accounts = staticmethod(get_accounts)
    get_products = staticmethod(get_products)
    get_performance = staticmethod(get_performance)
    get_account_status = staticmethod(get_account_status)
    get_product_statuses = staticmethod(get_product_statuses)
