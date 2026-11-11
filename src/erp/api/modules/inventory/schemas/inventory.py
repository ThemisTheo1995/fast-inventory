from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from erp.core.filter import TableFilter


class InventoryUpdate(BaseModel):
    """Fields that can be updated on an inventory record."""

    is_deleted: bool


class InventoryResponse(BaseModel):
    """Payload returned to the client for an inventory balance in a bin."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    workspace_id: UUID
    item_id: UUID
    bin_id: UUID
    quantity_on_hand: int
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)


class InventoryPaginatedResponse(BaseModel):
    """Payload for paginated inventory lists."""

    items: list[InventoryResponse]
    total: int
    filters: list[TableFilter] = Field(default_factory=list)
