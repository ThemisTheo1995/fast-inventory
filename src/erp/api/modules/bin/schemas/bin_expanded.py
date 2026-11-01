from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .bin import BinResponse


class ItemSummary(BaseModel):
    """Lightweight summary of an item."""

    id: UUID
    title: str
    sku: str
    unit_of_measure: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BinInventoryItemResponse(BaseModel):
    """Inventory record representation inside a bin detail response."""

    id: UUID
    quantity_on_hand: int
    item_id: UUID
    item: ItemSummary | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BinExpandedResponse(BinResponse):
    """Fully expanded bin response including inventory items and their nested item data."""

    inventory_items: list[BinInventoryItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BinExpandedPaginatedResponse(BaseModel):
    """Paginated response for expanded bin lists."""

    items: list[BinExpandedResponse]
    total: int
