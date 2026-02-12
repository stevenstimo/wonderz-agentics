"""
UnifiedToolBridge: Translates unified tool calls to platform-specific adapters.

Agents never know about Shopify, WordPress, etc. The bridge handles that translation.
"""

from typing import Dict, Any, Optional
from models.unified import UnifiedProduct
from tools.adapters import BaseAdapter, ShopifyAdapter, WordPressAdapter


class UnifiedToolBridge:
    """
    Provides a unified interface for agents to interact with any platform.
    
    Internally routes calls to the correct adapter based on the platform.
    """

    def __init__(self, adapters: Optional[Dict[str, BaseAdapter]] = None):
        """
        Initialize with a mapping of platform -> adapter.
        
        Args:
            adapters: Dict like {"shopify": ShopifyAdapter(...), "wordpress": WordPressAdapter(...)}
                      If None, will attempt to auto-instantiate based on platform name
        """
        self.adapters = adapters or {}

    def _get_adapter(self, platform: str) -> BaseAdapter:
        """Get the adapter for a given platform."""
        if platform not in self.adapters:
            # Try to instantiate a default adapter
            if platform.lower() == "shopify":
                self.adapters[platform] = ShopifyAdapter()
            elif platform.lower() == "wordpress":
                self.adapters[platform] = WordPressAdapter()
            else:
                raise ValueError(f"No adapter available for platform: {platform}")
        return self.adapters[platform]

    async def read_product(
        self, 
        platform: str, 
        product_id: str, 
        store_id: Optional[str] = None
    ) -> UnifiedProduct:
        """
        Read a product from any platform.
        
        Args:
            platform: "shopify", "wordpress", etc.
            product_id: The external product ID
            store_id: Optional store identifier for multi-store setups
        
        Returns:
            UnifiedProduct representation
        """
        adapter = self._get_adapter(platform)
        return await adapter.read_product(product_id, store_id)

    async def write_product(
        self, 
        platform: str, 
        product: UnifiedProduct, 
        store_id: Optional[str] = None
    ) -> bool:
        """
        Write/update a product on any platform.
        
        Args:
            platform: "shopify", "wordpress", etc.
            product: UnifiedProduct with new data
            store_id: Optional store identifier
        
        Returns:
            True if successful
        """
        adapter = self._get_adapter(platform)
        return await adapter.write_product(product, store_id)

    async def read_products(
        self,
        platform: str,
        store_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> list[UnifiedProduct]:
        """
        Read multiple products from a platform.
        
        Args:
            platform: "shopify", "wordpress", etc.
            store_id: Optional store identifier
            filters: Optional query filters
        
        Returns:
            List of UnifiedProduct objects
        """
        adapter = self._get_adapter(platform)
        if hasattr(adapter, "read_products"):
            return await adapter.read_products(store_id, filters)
        else:
            raise NotImplementedError(f"{platform} adapter does not support reading multiple products")

    async def read_product_metadata(
        self,
        platform: str,
        product_id: str,
        store_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Read metadata about a product (e.g., SEO info, analytics).
        
        Args:
            platform: "shopify", "wordpress", etc.
            product_id: The external product ID
            store_id: Optional store identifier
        
        Returns:
            Dict with metadata
        """
        adapter = self._get_adapter(platform)
        if hasattr(adapter, "read_product_metadata"):
            return await adapter.read_product_metadata(product_id, store_id)
        else:
            raise NotImplementedError(f"{platform} adapter does not support metadata reads")

    async def write_product_metadata(
        self,
        platform: str,
        product_id: str,
        metadata: Dict[str, Any],
        store_id: Optional[str] = None
    ) -> bool:
        """
        Update metadata on a product.
        
        Args:
            platform: "shopify", "wordpress", etc.
            product_id: The external product ID
            metadata: Dict of metadata to update
            store_id: Optional store identifier
        
        Returns:
            True if successful
        """
        adapter = self._get_adapter(platform)
        if hasattr(adapter, "write_product_metadata"):
            return await adapter.write_product_metadata(product_id, metadata, store_id)
        else:
            raise NotImplementedError(f"{platform} adapter does not support metadata writes")

    def set_adapter(self, platform: str, adapter: BaseAdapter):
        """Register a custom adapter for a platform."""
        self.adapters[platform] = adapter
