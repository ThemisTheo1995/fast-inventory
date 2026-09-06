# src/erp/api/modules/purchase_order/events.py
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine


@dataclass
class PurchaseOrderSentEvent:
    db: AsyncSession
    workspace_id: UUID
    purchase_order: PurchaseOrder


@dataclass
class PurchaseOrderReceivedEvent:
    db: AsyncSession
    workspace_id: UUID
    purchase_order: PurchaseOrder


@dataclass
class PurchaseOrderCancelledEvent:
    db: AsyncSession
    workspace_id: UUID
    purchase_order: PurchaseOrder


@dataclass
class PurchaseOrderReturnedEvent:
    db: AsyncSession
    workspace_id: UUID
    purchase_order: PurchaseOrder


@dataclass
class PurchaseOrderLineAddedEvent:
    db: AsyncSession
    workspace_id: UUID
    purchase_order: PurchaseOrder
    line: PurchaseOrderLine


@dataclass
class PurchaseOrderLineUpdatedEvent:
    db: AsyncSession
    workspace_id: UUID
    purchase_order: PurchaseOrder
    line: PurchaseOrderLine
    quantity_delta: int


@dataclass
class PurchaseOrderLineRemovedEvent:
    db: AsyncSession
    workspace_id: UUID
    purchase_order: PurchaseOrder
    line: PurchaseOrderLine
