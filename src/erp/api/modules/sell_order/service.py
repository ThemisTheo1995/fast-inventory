from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.erp.api.modules.sell_order.enums import SOStatusEnum
from src.erp.api.modules.sell_order.events import (
    SellOrderCancelledEvent,
    SellOrderConfirmedEvent,
    SellOrderFulfilledEvent,
    SellOrderLineAddedEvent,
    SellOrderLineRemovedEvent,
    SellOrderLineUpdatedEvent,
    SellOrderReturnedEvent,
)
from src.erp.api.modules.sell_order.exceptions import (
    SellOrderCannotDeleteError,
    SellOrderExistsError,
    SellOrderLineItemChangeError,
    SellOrderLineNotFoundError,
    SellOrderNotEditableError,
    SellOrderNotFoundError,
    SellOrderStatusTerminalError,
    SellOrderStatusTransitionError,
)
from src.erp.api.modules.sell_order.models import SellOrder, SellOrderLine
from src.erp.api.modules.sell_order.schemas import (
    SellOrderCreate,
    SellOrderLineCreate,
    SellOrderLineUpdate,
    SellOrderPaginatedResponse,
    SellOrderUpdate,
)
from src.erp.core.event_bus import EventBus

TRANSITION_EVENTS: dict[tuple[str, str], type] = {
    (SOStatusEnum.DRAFT, SOStatusEnum.CONFIRMED): SellOrderConfirmedEvent,
    (SOStatusEnum.CONFIRMED, SOStatusEnum.FULLFILLED): SellOrderFulfilledEvent,
    (SOStatusEnum.CONFIRMED, SOStatusEnum.CANCELLED): SellOrderCancelledEvent,
    (SOStatusEnum.CONFIRMED, SOStatusEnum.RETURNED): SellOrderReturnedEvent,
    (SOStatusEnum.FULLFILLED, SOStatusEnum.RETURNED): SellOrderReturnedEvent,
}


class SellOrderService:
    def __init__(self, db: Session, event_bus: EventBus) -> None:
        self.db = db
        self.event_bus = event_bus

    # ==============================================================================
    # INTERNAL HELPERS
    # ==============================================================================

    def _get_active_sell_order(self, workspace_id: UUID, sell_order_id: UUID, lock: bool = False) -> SellOrder:
        """Securely fetch a SO, enforcing workspace isolation and eagerly loading lines."""
        stmt = (
            select(SellOrder)
            .where(
                SellOrder.workspace_id == workspace_id,
                SellOrder.id == sell_order_id,
                SellOrder.is_deleted.is_(False),
            )
            .options(
                selectinload(SellOrder.sell_order_lines).selectinload(SellOrderLine.item),
                selectinload(SellOrder.customer),
            )
        )

        if lock:
            stmt = stmt.with_for_update()

        sell_order = self.db.execute(stmt).scalar_one_or_none()

        if not sell_order:
            raise SellOrderNotFoundError()
        return sell_order

    def _ensure_so_is_editable(self, so: SellOrder) -> None:
        if so.status in [SOStatusEnum.FULLFILLED, SOStatusEnum.CANCELLED, SOStatusEnum.RETURNED]:
            raise SellOrderNotEditableError(so.status)

    def _check_so_unique(self, workspace_id: UUID, so_number: str, exclude_sell_order_id: UUID | None = None) -> None:
        """Ensures SO number is unique within the workspace."""
        stmt = select(SellOrder).where(SellOrder.workspace_id == workspace_id, SellOrder.so_number == so_number)
        if exclude_sell_order_id:
            stmt = stmt.where(SellOrder.id != exclude_sell_order_id)

        if self.db.execute(stmt).scalar_one_or_none():
            raise SellOrderExistsError()

    def _recalculate_so_total(self, so: SellOrder) -> None:
        """Recalculates the SO total directly from memory. No database queries needed."""
        so.total_amount = sum(
            (line.quantity * line.unit_cost) for line in so.sell_order_lines if not getattr(line, "is_deleted", False)
        )

    def _validate_status_transition(self, old_status: SOStatusEnum, new_status: SOStatusEnum) -> None:
        """Enforces domain rules for status transitions."""
        if old_status in [SOStatusEnum.CANCELLED, SOStatusEnum.RETURNED]:
            raise SellOrderStatusTerminalError(old_status)

        if old_status == SOStatusEnum.FULLFILLED and new_status != SOStatusEnum.RETURNED:
            raise SellOrderStatusTransitionError(old_status.label, new_status.label)

    # ==============================================================================
    # HEADER OPERATIONS
    # ==============================================================================

    def create_sell_order(self, workspace_id: UUID, data: SellOrderCreate) -> SellOrder:
        """Creates a SO and its nested lines in a single atomic transaction."""
        self._check_so_unique(workspace_id, data.so_number)

        so_data = data.model_dump(exclude={"sell_order_lines"})
        lines_data = data.sell_order_lines

        sell_order = SellOrder(workspace_id=workspace_id, **so_data)

        for line_data in lines_data:
            line = SellOrderLine(**line_data.model_dump())
            sell_order.sell_order_lines.append(line)

        self._recalculate_so_total(sell_order)

        self.db.add(sell_order)
        self.db.commit()
        self.db.refresh(sell_order)

        return sell_order

    def get_sell_orders(
        self, workspace_id: UUID, search: str | None = None, page: int = 1, limit: int = 20
    ) -> SellOrderPaginatedResponse:
        """Fetches paginated SOs with lines eager-loaded."""
        base_query = select(SellOrder).where(
            SellOrder.workspace_id == workspace_id,
            SellOrder.is_deleted.is_(False),
        )

        if search:
            base_query = base_query.where(SellOrder.so_number.ilike(f"%{search}%"))

        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        skip = (page - 1) * limit
        sell_orders_query = (
            base_query.options(selectinload(SellOrder.sell_order_lines))
            .order_by(SellOrder.created_at.desc(), SellOrder.id.desc())
            .offset(skip)
            .limit(limit)
        )
        sell_orders = list(self.db.execute(sell_orders_query).scalars().all())

        return SellOrderPaginatedResponse(items=sell_orders, total=total)

    def get_sell_order(self, workspace_id: UUID, sell_order_id: UUID) -> SellOrder:
        return self._get_active_sell_order(workspace_id, sell_order_id)

    def update_sell_order(self, workspace_id: UUID, sell_order_id: UUID, data: SellOrderUpdate) -> SellOrder:
        """Applies partial updates to SO metadata and publishes transition events."""
        so = self._get_active_sell_order(workspace_id, sell_order_id, lock=True)
        update_data = data.model_dump(exclude_unset=True)

        if "so_number" in update_data and update_data["so_number"] != so.so_number:
            self._check_so_unique(workspace_id, update_data["so_number"], exclude_sell_order_id=sell_order_id)

        old_status = SOStatusEnum(so.status)
        new_status = SOStatusEnum(update_data.get("status", old_status))

        event_to_publish = None
        if old_status != new_status:
            self._validate_status_transition(old_status, new_status)
            transition_key = (old_status, new_status)

            if transition_key not in TRANSITION_EVENTS:
                raise SellOrderStatusTransitionError(old_status.label, new_status.label)

            event_class = TRANSITION_EVENTS[transition_key]
            event_to_publish = event_class(db=self.db, workspace_id=workspace_id, sell_order=so)

        for key, value in update_data.items():
            setattr(so, key, value)

        self.db.add(so)

        if event_to_publish:
            self.event_bus.publish(event_to_publish)

        self.db.commit()
        self.db.refresh(so)
        return so

    def delete_sell_order(self, workspace_id: UUID, sell_order_id: UUID) -> None:
        """Soft-deletes a SO and cascades the soft-delete to its lines."""
        so = self._get_active_sell_order(workspace_id, sell_order_id, lock=True)

        if so.status not in [SOStatusEnum.DRAFT, SOStatusEnum.CANCELLED]:
            raise SellOrderCannotDeleteError(so.status.label)

        for line in so.sell_order_lines:
            line.soft_delete()

        so.soft_delete()
        self.db.commit()

    # ==============================================================================
    # LINE OPERATIONS
    # ==============================================================================

    def add_line(self, workspace_id: UUID, sell_order_id: UUID, data: SellOrderLineCreate) -> SellOrderLine:
        so = self._get_active_sell_order(workspace_id, sell_order_id, lock=True)
        self._ensure_so_is_editable(so)

        new_line = SellOrderLine(sell_order_id=sell_order_id, **data.model_dump())
        so.sell_order_lines.append(new_line)
        self.db.add(new_line)

        self._recalculate_so_total(so)

        if so.status == SOStatusEnum.CONFIRMED and new_line.item_id:
            event = SellOrderLineAddedEvent(db=self.db, workspace_id=workspace_id, sell_order=so, line=new_line)
            self.event_bus.publish(event)

        self.db.commit()
        self.db.refresh(new_line)
        return new_line

    def update_line(
        self, workspace_id: UUID, sell_order_id: UUID, line_id: UUID, data: SellOrderLineUpdate
    ) -> SellOrderLine:
        so = self._get_active_sell_order(workspace_id, sell_order_id, lock=True)
        self._ensure_so_is_editable(so)

        line = next(
            (
                sell_order_line
                for sell_order_line in so.sell_order_lines
                if sell_order_line.id == line_id and not getattr(sell_order_line, "is_deleted", False)
            ),
            None,
        )
        if not line:
            raise SellOrderLineNotFoundError()

        update_data = data.model_dump(exclude_unset=True)

        if "item_id" in update_data and update_data["item_id"] != line.item_id:
            raise SellOrderLineItemChangeError()

        delta = 0
        if so.status == SOStatusEnum.CONFIRMED and "quantity" in update_data and line.item_id:
            delta = update_data["quantity"] - line.quantity

        for key, value in update_data.items():
            setattr(line, key, value)

        self.db.add(line)

        if "quantity" in update_data or "unit_cost" in update_data:
            self._recalculate_so_total(so)

        if delta != 0:
            event = SellOrderLineUpdatedEvent(
                db=self.db, workspace_id=workspace_id, sell_order=so, line=line, quantity_delta=delta
            )
            self.event_bus.publish(event)

        self.db.commit()
        self.db.refresh(line)
        return line

    def remove_line(self, workspace_id: UUID, sell_order_id: UUID, line_id: UUID) -> None:
        so = self._get_active_sell_order(workspace_id, sell_order_id, lock=True)
        self._ensure_so_is_editable(so)

        line = next(
            (
                sell_order_line
                for sell_order_line in so.sell_order_lines
                if sell_order_line.id == line_id and not getattr(sell_order_line, "is_deleted", False)
            ),
            None,
        )

        if not line:
            raise SellOrderLineNotFoundError()

        so.sell_order_lines.remove(line)
        self.db.delete(line)

        self._recalculate_so_total(so)

        if so.status == SOStatusEnum.CONFIRMED and line.item_id:
            event = SellOrderLineRemovedEvent(db=self.db, workspace_id=workspace_id, sell_order=so, line=line)
            self.event_bus.publish(event)

        self.db.commit()
