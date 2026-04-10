from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EbayStatusEnum(StrEnum):
    ACTIVE = "ACTIVE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    INACTIVE = "INACTIVE"
    PENDING = "PENDING"


# --- Shared Base Components ---

class EbayPrice(BaseModel):
    value: float
    currency: str = "GBP"


# --- ERP Standard Schemas ---

class EbayItem(BaseModel):
    """
    Standard ERP representation of a marketplace item.
    Mapped from eBay Inventory/Offer data.
    """
    external_id: str = Field(..., description="The listingId or offerId from the marketplace")
    sku: str = Field(..., description="The unique seller-defined SKU")
    marketplace: str = Field(default="eBay", description="Marketplace name")
    name: str = Field(..., description="Title of the item as it appears on the listing")
    price: EbayPrice
    stock_quantity: int = Field(default=0)
    status: EbayStatusEnum
    image_url: str | None = None
    last_synced_at: datetime = Field(default_factory=datetime.now)

    metadata: dict[str, list[str]] = Field(default_factory=dict)


class EbayCreateItem(BaseModel):
    """
    Input schema for triggering the 3-step eBay creation process.
    """
    sku: str
    name: str = Field(..., min_length=1, max_length=80)
    description: str
    price: float
    currency: str = "GBP"
    quantity: int = 0
    category_id: str = Field(..., description="eBay Category ID, e.g., '31387'")
    image_urls: list[str] = Field(default_factory=list)

    # Required for Step 2 (The Offer)
    fulfillment_policy_id: str = Field(..., description="eBay Shipping Policy ID")
    return_policy_id: str = Field(..., description="eBay Return Policy ID")
    payment_policy_id: str = Field(..., description="eBay Payment Policy ID")
