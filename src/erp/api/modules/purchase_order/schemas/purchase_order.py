from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from erp.api.modules.item.schemas import ItemResponse
from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.supplier.schemas import SupplierResponse
from erp.core.filter import TableFilter

# =======================================================
# Common Types
# =======================================================

PoNumber = Annotated[str, Field(max_length=100)]
Quantity = Annotated[int, Field(ge=1)]
Price = Annotated[int, Field(ge=0)]


# =======================================================
# Purchase Order Lines
# =======================================================


class PurchaseOrderLineBase(BaseModel):
    item_id: UUID | None = None
    quantity: Quantity
    unit_cost: Price


class PurchaseOrderLineCreate(PurchaseOrderLineBase):
    """Payload for creating/adding a line to an order."""

    pass


class PurchaseOrderLineUpdate(PurchaseOrderLineBase):
    """Payload for updating an existing purchase order line."""

    pass


class PurchaseOrderLineResponse(PurchaseOrderLineBase):
    """Response payload including the related item details."""

    id: UUID
    purchase_order_id: UUID
    item: ItemResponse | None = None

    model_config = ConfigDict(from_attributes=True)


# =======================================================
# Purchase Order
# =======================================================


class PurchaseOrderBase(BaseModel):
    po_number: PoNumber
    supplier_id: UUID | None = None
    status: POStatusEnum = POStatusEnum.DRAFT


class PurchaseOrderCreate(PurchaseOrderBase):
    """Payload for creating a PO with lines nested."""

    purchase_order_lines: list[PurchaseOrderLineCreate]


class PurchaseOrderUpdate(BaseModel):
    """Payload for partial updates to a PO header."""

    po_number: PoNumber | None = None
    supplier_id: UUID | None = None
    status: POStatusEnum | None = None


class PurchaseOrderResponse(PurchaseOrderBase):
    """Full payload returned to the client."""

    id: UUID
    workspace_id: UUID
    total_amount: int
    created_at: datetime
    updated_at: datetime

    # Relationships
    purchase_order_lines: list[PurchaseOrderLineResponse]
    supplier: SupplierResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderPaginatedResponse(BaseModel):
    """Payload for paginated PO lists."""

    items: list[PurchaseOrderResponse]
    total: int
    filters: list[TableFilter] = Field(default_factory=list)
