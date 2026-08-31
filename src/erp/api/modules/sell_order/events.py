from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from src.erp.api.modules.sell_order.models import SellOrder, SellOrderLine


@dataclass
class SellOrderConfirmedEvent:
    db: Session
    workspace_id: UUID
    sell_order: SellOrder


@dataclass
class SellOrderFulfilledEvent:
    db: Session
    workspace_id: UUID
    sell_order: SellOrder


@dataclass
class SellOrderCancelledEvent:
    db: Session
    workspace_id: UUID
    sell_order: SellOrder


@dataclass
class SellOrderReturnedEvent:
    db: Session
    workspace_id: UUID
    sell_order: SellOrder


@dataclass
class SellOrderLineAddedEvent:
    db: Session
    workspace_id: UUID
    sell_order: SellOrder
    line: SellOrderLine


@dataclass
class SellOrderLineUpdatedEvent:
    db: Session
    workspace_id: UUID
    sell_order: SellOrder
    line: SellOrderLine
    quantity_delta: int


@dataclass
class SellOrderLineRemovedEvent:
    db: Session
    workspace_id: UUID
    sell_order: SellOrder
    line: SellOrderLine
