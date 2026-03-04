from abc import ABC, abstractmethod
from typing import Any
from models.unified import UnifiedProduct

class BaseAdapter(ABC):
    """Abstracte adapter-interface voor alle platformen."""
    @abstractmethod
    async def get_product(self, product_id: str) -> UnifiedProduct:
        pass

    @abstractmethod
    async def update_product(self, product: UnifiedProduct) -> Any:
        pass

class ShopifyAdapter(BaseAdapter):
    """Adapter voor Shopify, vertaalt naar UnifiedProduct."""
    def __init__(self, shopify_client):
        self.client = shopify_client

    async def get_product(self, product_id: str) -> UnifiedProduct:
        # Haal Shopify product op en vertaal naar UnifiedProduct
        data = await self.client.get_product(product_id)
        return UnifiedProduct(
            external_id=data['id'],
            source_platform='shopify',
            title=data['title'],
            description_html=data.get('body_html', ''),
            price=float(data['variants'][0]['price']),
            currency=data['variants'][0].get('currency', 'EUR'),
            inventory_quantity=data['variants'][0].get('inventory_quantity', 0),
            seo_title=data.get('seo', {}).get('title'),
            seo_description=data.get('seo', {}).get('description'),
            tags=data.get('tags', '').split(',') if data.get('tags') else [],
            attributes={},
        )

    async def update_product(self, product: UnifiedProduct) -> Any:
        # Vertaal UnifiedProduct naar Shopify payload en update
        payload = {
            'id': product.external_id,
            'title': product.title,
            'body_html': product.description_html,
            'variants': [{
                'price': str(product.price),
                'inventory_quantity': product.inventory_quantity,
                'currency': product.currency,
            }],
            'tags': ','.join(product.tags),
            # ...andere velden indien nodig
        }
        return await self.client.update_product(payload)

class WordPressAdapter(BaseAdapter):
    """Adapter voor WooCommerce, vertaalt naar UnifiedProduct."""
    def __init__(self, wp_client):
        self.client = wp_client

    async def get_product(self, product_id: str) -> UnifiedProduct:
        data = await self.client.get_product(product_id)
        return UnifiedProduct(
            external_id=data['id'],
            source_platform='wordpress',
            title=data['name'],
            description_html=data.get('description', ''),
            price=float(data['price']),
            currency=data.get('currency', 'EUR'),
            inventory_quantity=int(data.get('stock_quantity', 0)),
            seo_title=data.get('seo_title'),
            seo_description=data.get('seo_description'),
            tags=data.get('tags', []),
            attributes=data.get('attributes', {}),
        )

    async def update_product(self, product: UnifiedProduct) -> Any:
        payload = {
            'id': product.external_id,
            'name': product.title,
            'description': product.description_html,
            'price': str(product.price),
            'stock_quantity': product.inventory_quantity,
            'tags': product.tags,
            'attributes': product.attributes,
            # ...andere velden indien nodig
        }
        return await self.client.update_product(payload)
