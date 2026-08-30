from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.erp.api.modules.purchase_order.enums import POStatusEnum
from src.erp.api.modules.purchase_order.events import (
    PurchaseOrderCancelledEvent,
    PurchaseOrderLineAddedEvent,
    PurchaseOrderLineRemovedEvent,
    PurchaseOrderLineUpdatedEvent,
    PurchaseOrderReceivedEvent,
    PurchaseOrderReturnedEvent,
    PurchaseOrderSentEvent,
)
from src.erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderCannotDeleteError,
    PurchaseOrderExistsError,
    PurchaseOrderLineItemChangeError,
    PurchaseOrderLineNotFoundError,
    PurchaseOrderNotEditableError,
    PurchaseOrderNotFoundError,
    PurchaseOrderStatusTransitionError,
)
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine
from src.erp.api.modules.purchase_order.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineUpdate,
    PurchaseOrderPaginatedResponse,
    PurchaseOrderUpdate,
)
from src.erp.core.event_bus import EventBus

TRANSITION_EVENTS: dict[tuple[str, str], type] = {
    (POStatusEnum.DRAFT, POStatusEnum.SENT): PurchaseOrderSentEvent,
    (POStatusEnum.SENT, POStatusEnum.RECEIVED): PurchaseOrderReceivedEvent,
    (POStatusEnum.SENT, POStatusEnum.CANCELLED): PurchaseOrderCancelledEvent,
    (POStatusEnum.RECEIVED, POStatusEnum.RETURNED): PurchaseOrderReturnedEvent,
}


class PurchaseOrderService:
    def __init__(self, db: Session, event_bus: EventBus) -> None:
        self.db = db
        self.event_bus = event_bus

    # ==============================================================================
    # INTERNAL HELPERS
    # ==============================================================================

    def _get_active_purchase_order(
        self, workspace_id: UUID, purchase_order_id: UUID, lock: bool = False
    ) -> PurchaseOrder:
        """Securely fetch a PO, enforcing workspace isolation and eagerly loading lines."""
        stmt = (
            select(PurchaseOrder)
            .where(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.id == purchase_order_id,
                PurchaseOrder.is_deleted.is_(False),
            )
            .options(
                selectinload(PurchaseOrder.purchase_order_lines).selectinload(PurchaseOrderLine.item),
                selectinload(PurchaseOrder.supplier),
            )
        )

        if lock:
            stmt = stmt.with_for_update()

        purchase_order = self.db.execute(stmt).scalar_one_or_none()

        if not purchase_order:
            raise PurchaseOrderNotFoundError()
        return purchase_order

    def _ensure_po_is_editable(self, po: PurchaseOrder) -> None:
        if po.status in [POStatusEnum.RECEIVED, POStatusEnum.CANCELLED, POStatusEnum.RETURNED]:
            raise PurchaseOrderNotEditableError(po.status)

    def _check_po_unique(
        self, workspace_id: UUID, po_number: str, exclude_purchase_order_id: UUID | None = None
    ) -> None:
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.workspace_id == workspace_id, PurchaseOrder.po_number == po_number
        )
        if exclude_purchase_order_id:
            stmt = stmt.where(PurchaseOrder.id != exclude_purchase_order_id)

        if self.db.execute(stmt).scalar_one_or_none():
            raise PurchaseOrderExistsError()

    def _recalculate_po_total(self, po: PurchaseOrder) -> None:
        """Recalculates the PO total directly from memory. No database queries needed."""
        po.total_amount = sum(
            (line.quantity * line.unit_cost)
            for line in po.purchase_order_lines
            if not getattr(line, "is_deleted", False)
        )

    # ==============================================================================
    # HEADER OPERATIONS
    # ==============================================================================

    def create_purchase_order(self, workspace_id: UUID, data: PurchaseOrderCreate) -> PurchaseOrder:
        self._check_po_unique(workspace_id, data.po_number)

        po_data = data.model_dump(exclude={"purchase_order_lines"})
        lines_data = data.purchase_order_lines

        purchase_order = PurchaseOrder(workspace_id=workspace_id, **po_data)

        for line_data in lines_data:
            line = PurchaseOrderLine(**line_data.model_dump())
            purchase_order.purchase_order_lines.append(line)

        self._recalculate_po_total(purchase_order)

        self.db.add(purchase_order)
        self.db.commit()
        self.db.refresh(purchase_order)

        return purchase_order

    def get_purchase_orders(
        self, workspace_id: UUID, search: str | None = None, page: int = 1, limit: int = 20
    ) -> PurchaseOrderPaginatedResponse:
        base_query = select(PurchaseOrder).where(
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrder.is_deleted.is_(False),
        )

        if search:
            base_query = base_query.where(PurchaseOrder.po_number.ilike(f"%{search}%"))

        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        skip = (page - 1) * limit
        purchase_orders_query = (
            base_query.options(selectinload(PurchaseOrder.purchase_order_lines))
            .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
            .offset(skip)
            .limit(limit)
        )
        purchase_orders = list(self.db.execute(purchase_orders_query).scalars().all())

        return PurchaseOrderPaginatedResponse(items=purchase_orders, total=total)

    def get_purchase_order(self, workspace_id: UUID, purchase_order_id: UUID) -> PurchaseOrder:
        return self._get_active_purchase_order(workspace_id, purchase_order_id)

    def update_purchase_order(
        self, workspace_id: UUID, purchase_order_id: UUID, data: PurchaseOrderUpdate
    ) -> PurchaseOrder:
        po = self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)
        update_data = data.model_dump(exclude_unset=True)

        if "po_number" in update_data and update_data["po_number"] != po.po_number:
            self._check_po_unique(workspace_id, update_data["po_number"], exclude_purchase_order_id=purchase_order_id)

        old_status = po.status
        new_status = update_data.get("status", old_status)

        event_to_publish = None
        event_to_publish = None
        if old_status != new_status:
            transition_key = (old_status, new_status)
            if transition_key not in TRANSITION_EVENTS:
                raise PurchaseOrderStatusTransitionError(old_status, new_status)

            event_class = TRANSITION_EVENTS[transition_key]
            event_to_publish = event_class(db=self.db, workspace_id=workspace_id, purchase_order=po)

        for key, value in update_data.items():
            setattr(po, key, value)

        self.db.add(po)

        if event_to_publish:
            self.event_bus.publish(event_to_publish)

        self.db.commit()
        self.db.refresh(po)
        return po

    def delete_purchase_order(self, workspace_id: UUID, purchase_order_id: UUID) -> None:
        po = self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)

        if po.status not in [POStatusEnum.DRAFT, POStatusEnum.CANCELLED]:
            raise PurchaseOrderCannotDeleteError(po.status.label)

        for line in po.purchase_order_lines:
            line.soft_delete()

        po.soft_delete()
        self.db.commit()

    # ==============================================================================
    # LINE OPERATIONS (Handled via the PO Aggregate)
    # ==============================================================================

    def add_line(self, workspace_id: UUID, purchase_order_id: UUID, data: PurchaseOrderLineCreate) -> PurchaseOrderLine:
        po = self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)
        self._ensure_po_is_editable(po)

        new_line = PurchaseOrderLine(purchase_order_id=purchase_order_id, **data.model_dump())
        po.purchase_order_lines.append(new_line)
        self.db.add(new_line)

        self._recalculate_po_total(po)

        if po.status == POStatusEnum.SENT and new_line.item_id:
            event = PurchaseOrderLineAddedEvent(db=self.db, workspace_id=workspace_id, purchase_order=po, line=new_line)
            self.event_bus.publish(event)

        self.db.commit()
        self.db.refresh(new_line)
        return new_line

    def update_line(
        self, workspace_id: UUID, purchase_order_id: UUID, line_id: UUID, data: PurchaseOrderLineUpdate
    ) -> PurchaseOrderLine:
        po = self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)
        self._ensure_po_is_editable(po)

        line = next(
            (
                purchase_order_line
                for purchase_order_line in po.purchase_order_lines
                if purchase_order_line.id == line_id and not getattr(purchase_order_line, "is_deleted", False)
            ),
            None,
        )
        if not line:
            raise PurchaseOrderLineNotFoundError()

        update_data = data.model_dump(exclude_unset=True)

        if "item_id" in update_data and update_data["item_id"] != line.item_id:
            raise PurchaseOrderLineItemChangeError()

        delta = 0
        if po.status == POStatusEnum.SENT and "quantity" in update_data and line.item_id:
            delta = update_data["quantity"] - line.quantity

        for key, value in update_data.items():
            setattr(line, key, value)

        self.db.add(line)

        if "quantity" in update_data or "unit_cost" in update_data:
            self._recalculate_po_total(po)

        if delta != 0:
            event = PurchaseOrderLineUpdatedEvent(
                db=self.db, workspace_id=workspace_id, purchase_order=po, line=line, quantity_delta=delta
            )
            self.event_bus.publish(event)

        self.db.commit()
        self.db.refresh(line)
        return line

    def remove_line(self, workspace_id: UUID, purchase_order_id: UUID, line_id: UUID) -> None:
        po = self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)
        self._ensure_po_is_editable(po)

        line = next(
            (
                purchase_order_line
                for purchase_order_line in po.purchase_order_lines
                if purchase_order_line.id == line_id and not getattr(purchase_order_line, "is_deleted", False)
            ),
            None,
        )

        if not line:
            raise PurchaseOrderLineNotFoundError()

        po.purchase_order_lines.remove(line)
        self.db.delete(line)

        self._recalculate_po_total(po)

        if po.status == POStatusEnum.SENT and line.item_id:
            event = PurchaseOrderLineRemovedEvent(db=self.db, workspace_id=workspace_id, purchase_order=po, line=line)
            self.event_bus.publish(event)

        self.db.commit()
