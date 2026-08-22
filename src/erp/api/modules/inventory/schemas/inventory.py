from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.erp.api.modules.item.schemas import ItemResponse


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
    item: ItemResponse | None = None

    # Hybrid proerties
    quantity_available: int
    expected_available: int

    model_config = ConfigDict(from_attributes=True)


class InventoryPaginatedResponse(BaseModel):
    """Payload for paginated inventory lists."""

    items: list[InventoryResponse]
    total: int
