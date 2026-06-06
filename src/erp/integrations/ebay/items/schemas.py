from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from erp.integrations.ebay.items.enums import EbayItemStatus


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
    workspace_id: UUID | None = Field(default=None, description="Associated ERP workspace UUID")
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
    """Payload expected from the client to create an item."""
    workspace_id: UUID
    external_id: str
    sku: str | None = None
    title: str
    description: str
    price: Decimal
    currency: str
    quantity: int = 0
    status: EbayItemStatus = EbayItemStatus.DRAFT
    images: list[str] = []


class EbayItemResponse(EbayCreateItem):
    """Payload returned to the client (includes DB-generated fields)."""
    id: UUID

    # Tells Pydantic it can read data directly from the SQLAlchemy ORM object
    model_config = ConfigDict(from_attributes=True)
