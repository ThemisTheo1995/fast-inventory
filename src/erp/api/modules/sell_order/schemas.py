from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from erp.api.modules.customer.schemas import CustomerResponse
from erp.api.modules.item.schemas import ItemResponse
from erp.api.modules.sell_order.enums import SOStatusEnum

# =======================================================
# Common Types
# =======================================================

SoNumber = Annotated[str, Field(max_length=100)]
Quantity = Annotated[int, Field(ge=1)]
Price = Annotated[int, Field(ge=0)]

# =======================================================
# Sell Order Lines
# =======================================================


class SellOrderLineBase(BaseModel):
    item_id: UUID | None = None
    quantity: Quantity
    unit_cost: Price


class SellOrderLineCreate(SellOrderLineBase):
    """Payload for creating/adding a line to an order."""

    pass


class SellOrderLineUpdate(SellOrderLineBase):
    """Payload for updating an existing sell order line."""

    pass


class SellOrderLineResponse(SellOrderLineBase):
    """Response payload including the related item details."""

    id: UUID
    sell_order_id: UUID
    item: ItemResponse | None = None

    model_config = ConfigDict(from_attributes=True)


# =======================================================
# Sell Order
# =======================================================


class SellOrderBase(BaseModel):
    so_number: SoNumber
    customer_id: UUID | None = None
    status: SOStatusEnum = SOStatusEnum.DRAFT


class SellOrderCreate(SellOrderBase):
    """Payload for creating a SO with lines nested."""

    sell_order_lines: list[SellOrderLineCreate]


class SellOrderUpdate(BaseModel):
    """Payload for partial updates to a SO header."""

    so_number: SoNumber | None = None
    customer_id: UUID | None = None
    status: SOStatusEnum | None = None


class SellOrderResponse(SellOrderBase):
    """Full payload returned to the client."""

    id: UUID
    workspace_id: UUID
    total_amount: int
    created_at: datetime
    updated_at: datetime

    # Relationships
    sell_order_lines: list[SellOrderLineResponse]
    customer: CustomerResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class SellOrderPaginatedResponse(BaseModel):
    """Payload for paginated SO lists."""

    items: list[SellOrderResponse]
    total: int
