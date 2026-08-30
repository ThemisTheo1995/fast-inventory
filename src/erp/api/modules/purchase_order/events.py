# src/erp/api/modules/purchase_order/events.py
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine


@dataclass
class PurchaseOrderSentEvent:
    db: Session
    workspace_id: UUID
    purchase_order: PurchaseOrder


@dataclass
class PurchaseOrderReceivedEvent:
    db: Session
    workspace_id: UUID
    purchase_order: PurchaseOrder


@dataclass
class PurchaseOrderCancelledEvent:
    db: Session
    workspace_id: UUID
    purchase_order: PurchaseOrder


@dataclass
class PurchaseOrderReturnedEvent:
    db: Session
    workspace_id: UUID
    purchase_order: PurchaseOrder


@dataclass
class PurchaseOrderLineAddedEvent:
    db: Session
    workspace_id: UUID
    purchase_order: PurchaseOrder
    line: PurchaseOrderLine


@dataclass
class PurchaseOrderLineUpdatedEvent:
    db: Session
    workspace_id: UUID
    purchase_order: PurchaseOrder
    line: PurchaseOrderLine
    quantity_delta: int


@dataclass
class PurchaseOrderLineRemovedEvent:
    db: Session
    workspace_id: UUID
    purchase_order: PurchaseOrder
    line: PurchaseOrderLine
