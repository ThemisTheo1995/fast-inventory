from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.erp.api.modules.inventory.enums import OrderType

# --- Inventory Schemas ---


class InventoryResponse(BaseModel):
    """Payload returned to the client for an inventory balance."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    workspace_id: UUID
    item_id: UUID
    quantity_on_hand: int
    quantity_allocated: int
    quantity_on_order: int

    # Hybrid proerties
    quantity_available: int
    expected_available: int

    model_config = ConfigDict(from_attributes=True)


class InventoryPaginatedResponse(BaseModel):
    """Payload for paginated inventory lists."""

    items: list[InventoryResponse]
    total: int


# --- Stock Movement Schemas ---


class StockMovementCreate(BaseModel):
    """Payload for creating a new stock movement (adjusts inventory)."""

    item_id: UUID
    quantity_change: int
    reference_type: OrderType
    reference_id: UUID | None = None


class StockMovementResponse(BaseModel):
    """Payload returned to the client for a stock movement record."""

    id: UUID
    workspace_id: UUID
    item_id: UUID
    quantity_change: int
    reference_type: OrderType
    reference_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockMovementPaginatedResponse(BaseModel):
    """Payload for paginated stock movement lists."""

    items: list[StockMovementResponse]
    total: int
