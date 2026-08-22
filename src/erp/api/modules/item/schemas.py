from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.erp.api.modules.inventory.schemas.stock_movement import StockMovementResponse

Title = Annotated[str | None, Field(default=None, max_length=255)]
Sku = Annotated[str | None, Field(default=None, max_length=100)]
BasePrice = Annotated[int | None, Field(default=None, ge=0)]


# =======================================================
# Mappers (for integrations)
# =======================================================


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


# =======================================================
# Common
# =======================================================


class ItemBase(BaseModel):
    title: Title
    sku: Sku
    base_price: BasePrice


class ItemResponse(BaseModel):
    """Payload returned to the client."""

    id: UUID
    workspace_id: UUID
    title: str
    sku: str
    base_price: int | None
    created_at: datetime
    updated_at: datetime
    stock_movements: list[StockMovementResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ItemPaginatedResponse(BaseModel):
    """Payload for paginated item lists."""

    items: list[ItemResponse]
    total: int


# =======================================================
# Create Item
# =======================================================


class ItemCreate(ItemBase):
    """Payload for creating a new item."""

    pass


# =======================================================
# Update Item
# =======================================================


class ItemUpdate(ItemBase):
    """Payload for updating an item."""

    pass
