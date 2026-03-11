from abc import ABC, abstractmethod
from typing import Any, Optional
from models.unified import UnifiedProduct
import logging

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """Abstracte adapter-interface voor alle platformen."""

    @abstractmethod
    async def get_product(self, product_id: str) -> UnifiedProduct:
        pass

    @abstractmethod
    async def update_product(self, product: UnifiedProduct) -> Any:
        pass


class ShopifyAdapter(BaseAdapter):
    """Adapter voor Shopify. Werkt met echte client of als stub."""

    def __init__(self, shopify_client=None):
        self.client = shopify_client

    async def get_product(self, product_id: str) -> UnifiedProduct:
        if self.client is None:
            logger.info("ShopifyAdapter stub: get_product(%s)", product_id)
            return UnifiedProduct(
                external_id=product_id,
                source_platform="shopify",
                title=f"[Shopify Stub] Product {product_id}",
                description_html="<p>Stub product - geen echte Shopify connectie</p>",
                price=0.0,
                currency="EUR",
                inventory_quantity=0,
            )
        data = await self.client.get_product(product_id)
        return UnifiedProduct(
            external_id=data["id"],
            source_platform="shopify",
            title=data["title"],
            description_html=data.get("body_html", ""),
            price=float(data["variants"][0]["price"]),
            currency=data["variants"][0].get("currency", "EUR"),
            inventory_quantity=data["variants"][0].get("inventory_quantity", 0),
            seo_title=data.get("seo", {}).get("title"),
            seo_description=data.get("seo", {}).get("description"),
            tags=data.get("tags", "").split(",") if data.get("tags") else [],
            attributes={},
        )

    async def update_product(self, product: UnifiedProduct) -> Any:
        if self.client is None:
            logger.info("ShopifyAdapter stub: update_product(%s)", product.external_id)
            return True
        payload = {
            "id": product.external_id,
            "title": product.title,
            "body_html": product.description_html,
            "variants": [
                {
                    "price": str(product.price),
                    "inventory_quantity": product.inventory_quantity,
                    "currency": product.currency,
                }
            ],
            "tags": ",".join(product.tags),
        }
        return await self.client.update_product(payload)


class WordPressAdapter(BaseAdapter):
    """Adapter voor WooCommerce. Werkt met echte client of als stub."""

    def __init__(self, wp_client=None):
        self.client = wp_client

    async def get_product(self, product_id: str) -> UnifiedProduct:
        if self.client is None:
            logger.info("WordPressAdapter stub: get_product(%s)", product_id)
            return UnifiedProduct(
                external_id=product_id,
                source_platform="wordpress",
                title=f"[WordPress Stub] Product {product_id}",
                description_html="<p>Stub product - geen echte WordPress connectie</p>",
                price=0.0,
                currency="EUR",
                inventory_quantity=0,
            )
        data = await self.client.get_product(product_id)
        return UnifiedProduct(
            external_id=data["id"],
            source_platform="wordpress",
            title=data["name"],
            description_html=data.get("description", ""),
            price=float(data["price"]),
            currency=data.get("currency", "EUR"),
            inventory_quantity=int(data.get("stock_quantity", 0)),
            seo_title=data.get("seo_title"),
            seo_description=data.get("seo_description"),
            tags=data.get("tags", []),
            attributes=data.get("attributes", {}),
        )

    async def update_product(self, product: UnifiedProduct) -> Any:
        if self.client is None:
            logger.info("WordPressAdapter stub: update_product(%s)", product.external_id)
            return True
        payload = {
            "id": product.external_id,
            "name": product.title,
            "description": product.description_html,
            "price": str(product.price),
            "stock_quantity": product.inventory_quantity,
            "tags": product.tags,
            "attributes": product.attributes,
        }
        return await self.client.update_product(payload)


class CustomAdapter(BaseAdapter):
    """Generic adapter die mock data retourneert voor onbekende platformen."""

    def __init__(self, platform: str = "custom"):
        self.platform = platform

    async def get_product(self, product_id: str) -> UnifiedProduct:
        logger.info("CustomAdapter(%s): get_product(%s)", self.platform, product_id)
        return UnifiedProduct(
            external_id=product_id,
            source_platform=self.platform,
            title=f"[{self.platform}] Product {product_id}",
            description_html="<p>Mock product via CustomAdapter</p>",
            price=0.0,
            currency="EUR",
            inventory_quantity=0,
        )

    async def update_product(self, product: UnifiedProduct) -> Any:
        logger.info("CustomAdapter(%s): update_product(%s)", self.platform, product.external_id)
        return True


class AdapterFactory:
    """
    Factory die adapters aanmaakt op basis van platform naam.
    Standaard worden stub-adapters gebruikt (geen echte API calls).
    """

    _registry: dict[str, type[BaseAdapter]] = {
        "shopify": ShopifyAdapter,
        "wordpress": WordPressAdapter,
    }

    @classmethod
    def register(cls, platform: str, adapter_class: type[BaseAdapter]) -> None:
        cls._registry[platform] = adapter_class

    @classmethod
    def get(cls, platform: str, client: Optional[Any] = None) -> BaseAdapter:
        adapter_class = cls._registry.get(platform)
        if adapter_class is not None:
            if client is not None:
                return adapter_class(client)
            return adapter_class()
        return CustomAdapter(platform=platform)
