from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from erp.api.modules.inventory.schemas.stock_movement import StockMovementResponse
from erp.core.filter import TableFilter

# ==============================================================================
# FIELD TYPES
# ==============================================================================

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]

Sku = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]

BasePrice = Annotated[int, Field(ge=0)]


# ==============================================================================
# MARKETPLACE MAPPERS
# ==============================================================================


class MarketplaceItem(BaseModel):
    """Standard ERP representation of a marketplace item."""

    external_id: str = Field(..., description="ID from marketplace")
    marketplace: str = Field(..., description="Marketplace name, e.g. eBay")
    created_at: datetime = Field(..., description="UTC order creation datetime")


class MarketplaceCreateItem(BaseModel):
    """Basic marketplace item creation payload."""

    name: str = Field(..., min_length=1)


# ==============================================================================
# COMMON
# ==============================================================================


class ItemBase(BaseModel):
    """Common item fields."""

    title: Title
    sku: Sku
    base_price: BasePrice = 0


class ItemResponse(BaseModel):
    """Payload returned to the client."""

    id: UUID
    workspace_id: UUID
    title: str
    sku: str
    barcode_id: str | None = None
    base_price: int = 0
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    # Global commercial and physical metrics
    quantity_on_order: int = 0
    quantity_allocated: int = 0
    total_quantity_on_hand: int = 0

    stock_movements: list[StockMovementResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ItemPaginatedResponse(BaseModel):
    items: list[ItemResponse]
    total: int
    page: int = 1
    limit: int = 20
    filters: list[TableFilter] = Field(default_factory=list)


# ==============================================================================
# CREATE ITEM
# ==============================================================================


class ItemCreate(ItemBase):
    """Payload for creating a new item."""

    pass


# ==============================================================================
# BARCODE
# ==============================================================================


class ItemBarcode(BaseModel):
    """Payload for creating a new item barcode."""

    barcode_id: str = Field(..., min_length=1)
    workspace_id: UUID


# ==============================================================================
# UPDATE ITEM
# ==============================================================================


class ItemUpdate(BaseModel):
    title: Title | None = None
    sku: Sku | None = None
    base_price: BasePrice | None = None
    is_deleted: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_not_null_fields(self) -> object:
        for field in ("title", "sku", "base_price"):
            if field in self.model_fields_set and getattr(self, field) is None:
                msg = f"{field} cannot be null"
                raise ValueError(msg)

        return self
