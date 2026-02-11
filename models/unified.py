from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class UnifiedProduct(BaseModel):
    """Universele representatie van een product voor alle platformen."""
    external_id: str
    source_platform: str = Field(..., description="shopify, wordpress, or custom")
    title: str
    description_html: str
    price: float
    currency: str = "EUR"
    inventory_quantity: int
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    tags: List[str] = []
    attributes: Dict[str, str] = Field(default_factory=dict, description="Custom velden")

class UnifiedAd(BaseModel):
    """Universele representatie van een advertentie (Meta, Google, etc.)."""
    ad_id: str
    platform: str # meta, google
    status: str # active, paused
    headline: str
    body_text: str
    spend: float
    conversions: int
    roas: float
