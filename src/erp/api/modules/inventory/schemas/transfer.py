from uuid import UUID

from pydantic import BaseModel, Field


class InventoryTransferRequest(BaseModel):
    item_id: UUID
    source_bin_id: UUID
    destination_bin_id: UUID
    quantity: int = Field(..., gt=0, description="Quantity to transfer must be greater than zero")
    notes: str | None = Field(None, max_length=255)
