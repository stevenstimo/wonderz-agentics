"""Shopify adapter - basis structuur voor agent integratie."""

import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ShopifyAdapter:
    """Minimale Shopify adapter. Vereist SHOPIFY_STORE_URL en SHOPIFY_ACCESS_TOKEN in .env.vm"""

    def __init__(self, store_url: str, access_token: str):
        self.store_url = store_url.rstrip("/")
        self.access_token = access_token
        self.base_url = f"{self.store_url}/admin/api/2024-01"

    async def get_products(self, limit: int = 50) -> list:
        """Haal producten op uit Shopify."""
        # TODO: implementeer na SHOPIFY_ACCESS_TOKEN in .env.vm
        raise NotImplementedError("Shopify adapter nog niet geconfigureerd")

    async def get_orders(self, limit: int = 50) -> list:
        """Haal orders op uit Shopify."""
        raise NotImplementedError("Shopify adapter nog niet geconfigureerd")