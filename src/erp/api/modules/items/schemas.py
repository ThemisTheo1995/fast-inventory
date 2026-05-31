from datetime import datetime

from pydantic import BaseModel, Field


class MarketplaceItem(BaseModel):
    """
    Standard ERP representation of a marketplace item.
    All adapters should map their raw marketplace data to this format.
    """

    external_id: str = Field(..., description="ID from marketplace")
    marketplace: str = Field(..., description="Marketplace name, e.g. eBay")
    created_at: datetime = Field(..., description="UTC order creation datetime")


class MarketplaceCreateItem(BaseModel):
    name: str = Field(..., description="Item name")
