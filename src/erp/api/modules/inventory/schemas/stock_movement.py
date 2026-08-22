from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.erp.api.modules.inventory.enums import OrderType


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
