from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarketplaceOrderItem(BaseModel):
    sku: str
    quantity: int
    price: Decimal


class MarketplaceOrder(BaseModel):
    """
    Standard ERP representation of a marketplace order.
    All adapters should map their raw marketplace data to this format.
    """

    external_id: str = Field(..., description="ID from marketplace")
    marketplace: str = Field(..., description="Marketplace name, e.g. eBay")
    total: Decimal = Field(..., description="Total order value")
    currency: str = Field(..., description="Currency code, e.g. USD")
    created_at: datetime = Field(..., description="UTC order creation datetime")
    items: list[MarketplaceOrderItem] = Field(default_factory=list)


class MarketplaceCreateOrderItem(BaseModel):
    sku: str
    quantity: int
    price: Decimal


class MarketplaceCreateOrder(BaseModel):
    items: list[MarketplaceCreateOrderItem] = Field(default_factory=list)
    total: Decimal = Field(..., description="Total order value")
    currency: str = Field(..., description="Currency code, e.g. USD")
