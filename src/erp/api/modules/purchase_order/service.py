from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from src.erp.api.modules.purchase_order.filters.purchase_order import PurchaseOrderFilter
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine
from src.erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineUpdate,
    PurchaseOrderPaginatedResponse,
    PurchaseOrderUpdate,
)
from src.erp.api.modules.supplier.models import Supplier
from src.erp.core.event_bus import EventBus

TRANSITION_EVENTS: dict[tuple[str, str], type] = {
    (POStatusEnum.DRAFT, POStatusEnum.SENT): PurchaseOrderSentEvent,
    (POStatusEnum.SENT, POStatusEnum.RECEIVED): PurchaseOrderReceivedEvent,
    (POStatusEnum.SENT, POStatusEnum.CANCELLED): PurchaseOrderCancelledEvent,
    (POStatusEnum.RECEIVED, POStatusEnum.RETURNED): PurchaseOrderReturnedEvent,
}


class PurchaseOrderService:
    def __init__(self, db: AsyncSession, event_bus: EventBus | None = None) -> None:
        self.db = db
        self.event_bus = event_bus

    # ==============================================================================
    # INTERNAL HELPERS
    # ==============================================================================

    async def _get_active_purchase_order(
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

        result = await self.db.execute(stmt)
        purchase_order = result.scalar_one_or_none()

        if not purchase_order:
            raise PurchaseOrderNotFoundError()
        return purchase_order

    def _ensure_po_is_editable(self, po: PurchaseOrder) -> None:
        if po.status in [POStatusEnum.RECEIVED, POStatusEnum.CANCELLED, POStatusEnum.RETURNED]:
            raise PurchaseOrderNotEditableError(po.status)

    async def _check_po_unique(
        self, workspace_id: UUID, po_number: str, exclude_purchase_order_id: UUID | None = None
    ) -> None:
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.workspace_id == workspace_id, PurchaseOrder.po_number == po_number
        )
        if exclude_purchase_order_id:
            stmt = stmt.where(PurchaseOrder.id != exclude_purchase_order_id)

        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
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

    async def create_purchase_order(self, workspace_id: UUID, data: PurchaseOrderCreate) -> PurchaseOrder:
        await self._check_po_unique(workspace_id, data.po_number)

        po_data = data.model_dump(exclude={"purchase_order_lines"})
        lines_data = data.purchase_order_lines

        purchase_order = PurchaseOrder(workspace_id=workspace_id, **po_data)

        for line_data in lines_data:
            line = PurchaseOrderLine(**line_data.model_dump())
            purchase_order.purchase_order_lines.append(line)

        self._recalculate_po_total(purchase_order)

        self.db.add(purchase_order)
        await self.db.commit()

        return await self._get_active_purchase_order(workspace_id, purchase_order.id)

    async def get_purchase_orders(
        self,
        workspace_id: UUID,
        filters: PurchaseOrderFilter | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PurchaseOrderPaginatedResponse:
        filters = filters or PurchaseOrderFilter()

        base_query = select(PurchaseOrder).where(
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrder.is_deleted.is_(False),
        )

        if search:
            search_term = f"%{search}%"
            base_query = base_query.outerjoin(PurchaseOrder.supplier).where(
                or_(
                    PurchaseOrder.po_number.ilike(search_term),
                    Supplier.name.ilike(search_term),
                    Supplier.email.ilike(search_term),
                )
            )

        base_query = filters.apply(base_query, PurchaseOrder)

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        skip = (page - 1) * limit
        purchase_orders_query = (
            base_query.options(
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.purchase_order_lines).selectinload(PurchaseOrderLine.item),
            )
            .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
            .offset(skip)
            .limit(limit)
        )
        purchase_orders_result = await self.db.execute(purchase_orders_query)
        purchase_orders = list(purchase_orders_result.scalars().all())

        table_filters = await filters.build_ui_filters(self.db, workspace_id)

        return PurchaseOrderPaginatedResponse(items=purchase_orders, total=total, filters=table_filters)

    async def get_purchase_order(self, workspace_id: UUID, purchase_order_id: UUID) -> PurchaseOrder:
        return await self._get_active_purchase_order(workspace_id, purchase_order_id)

    async def update_purchase_order(
        self, workspace_id: UUID, purchase_order_id: UUID, data: PurchaseOrderUpdate
    ) -> PurchaseOrder:
        po = await self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)
        update_data = data.model_dump(exclude_unset=True)

        if "po_number" in update_data and update_data["po_number"] != po.po_number:
            await self._check_po_unique(
                workspace_id, update_data["po_number"], exclude_purchase_order_id=purchase_order_id
            )

        old_status = po.status
        new_status = update_data.get("status", old_status)

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
            await self.event_bus.publish(event_to_publish)

        await self.db.commit()

        return await self._get_active_purchase_order(workspace_id, purchase_order_id)

    async def delete_purchase_order(self, workspace_id: UUID, purchase_order_id: UUID) -> None:
        po = await self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)

        if po.status not in [POStatusEnum.DRAFT, POStatusEnum.CANCELLED]:
            raise PurchaseOrderCannotDeleteError(po.status.label)

        for line in po.purchase_order_lines:
            line.soft_delete()

        po.soft_delete()
        await self.db.commit()

    # ==============================================================================
    # LINE OPERATIONS (Handled via the PO Aggregate)
    # ==============================================================================

    async def add_line(
        self, workspace_id: UUID, purchase_order_id: UUID, data: PurchaseOrderLineCreate
    ) -> PurchaseOrderLine:
        po = await self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)
        self._ensure_po_is_editable(po)

        new_line = PurchaseOrderLine(purchase_order_id=purchase_order_id, **data.model_dump())
        po.purchase_order_lines.append(new_line)
        self.db.add(new_line)

        self._recalculate_po_total(po)

        if po.status == POStatusEnum.SENT and new_line.item_id:
            event = PurchaseOrderLineAddedEvent(db=self.db, workspace_id=workspace_id, purchase_order=po, line=new_line)
            await self.event_bus.publish(event)

        await self.db.commit()

        stmt = (
            select(PurchaseOrderLine)
            .options(selectinload(PurchaseOrderLine.item))
            .where(PurchaseOrderLine.id == new_line.id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def update_line(
        self, workspace_id: UUID, purchase_order_id: UUID, line_id: UUID, data: PurchaseOrderLineUpdate
    ) -> PurchaseOrderLine:
        po = await self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)
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
            await self.event_bus.publish(event)

        await self.db.commit()

        stmt = (
            select(PurchaseOrderLine)
            .options(selectinload(PurchaseOrderLine.item))
            .where(PurchaseOrderLine.id == line.id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def remove_line(self, workspace_id: UUID, purchase_order_id: UUID, line_id: UUID) -> None:
        po = await self._get_active_purchase_order(workspace_id, purchase_order_id, lock=True)
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
        await self.db.delete(line)

        self._recalculate_po_total(po)

        if po.status == POStatusEnum.SENT and line.item_id:
            event = PurchaseOrderLineRemovedEvent(db=self.db, workspace_id=workspace_id, purchase_order=po, line=line)
            await self.event_bus.publish(event)

        await self.db.commit()
