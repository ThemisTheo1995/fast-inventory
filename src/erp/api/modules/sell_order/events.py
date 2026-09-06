from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.sell_order.models import SellOrder, SellOrderLine


@dataclass
class SellOrderConfirmedEvent:
    db: AsyncSession
    workspace_id: UUID
    sell_order: SellOrder


@dataclass
class SellOrderFulfilledEvent:
    db: AsyncSession
    workspace_id: UUID
    sell_order: SellOrder


@dataclass
class SellOrderCancelledEvent:
    db: AsyncSession
    workspace_id: UUID
    sell_order: SellOrder


@dataclass
class SellOrderReturnedEvent:
    db: AsyncSession
    workspace_id: UUID
    sell_order: SellOrder


@dataclass
class SellOrderLineAddedEvent:
    db: AsyncSession
    workspace_id: UUID
    sell_order: SellOrder
    line: SellOrderLine


@dataclass
class SellOrderLineUpdatedEvent:
    db: AsyncSession
    workspace_id: UUID
    sell_order: SellOrder
    line: SellOrderLine
    quantity_delta: int


@dataclass
class SellOrderLineRemovedEvent:
    db: AsyncSession
    workspace_id: UUID
    sell_order: SellOrder
    line: SellOrderLine
