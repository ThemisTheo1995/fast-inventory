from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.erp.api.modules.inventory.enums import OrderType
from src.erp.api.modules.inventory.schemas import StockMovementCreate
from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.sell_order.exceptions import (
    SellOrderExistsError,
    SellOrderLineNotFoundError,
    SellOrderNotFoundError,
)
from src.erp.api.modules.sell_order.models import SellOrder, SellOrderLine
from src.erp.api.modules.sell_order.schemas import (
    SellOrderCreate,
    SellOrderLineCreate,
    SellOrderLineUpdate,
    SellOrderPaginatedResponse,
    SellOrderUpdate,
)


class SellOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory_service = InventoryService(db)

    def _get_active_sell_order(self, workspace_id: UUID, sell_order_id: UUID) -> SellOrder:
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
        sell_order = self.db.execute(stmt).scalar_one_or_none()

        if not sell_order:
            raise SellOrderNotFoundError()
        return sell_order

    def _check_so_unique(self, workspace_id: UUID, so_number: str, exclude_sell_order_id: UUID | None = None) -> None:
        """Ensures SO number is unique within the workspace."""
        stmt = select(SellOrder).where(SellOrder.workspace_id == workspace_id, SellOrder.so_number == so_number)

        if exclude_sell_order_id:
            stmt = stmt.where(SellOrder.id != exclude_sell_order_id)

        if self.db.execute(stmt).scalar_one_or_none():
            raise SellOrderExistsError()

    def _handle_status_transition(self, workspace_id: UUID, so: SellOrder, old_status: str, new_status: str) -> None:
        if old_status in ["RECEIVED", "CANCELLED"]:
            raise ValueError(f"Cannot change status from terminal state: {old_status}")  # noqa

        for line in so.sell_order_lines:
            if not line.item_id:
                continue

            match (old_status, new_status):
                case ("DRAFT", "SENT"):
                    self.inventory_service.adjust_quantity_allocated(
                        workspace_id,
                        line.item_id,
                        line.quantity,
                    )

                case ("SENT", "RECEIVED"):
                    self.inventory_service.adjust_quantity_allocated(
                        workspace_id,
                        line.item_id,
                        -line.quantity,
                    )
                    self.inventory_service.create_stock_movement(
                        workspace_id,
                        StockMovementCreate(
                            item_id=line.item_id,
                            quantity_change=-line.quantity,
                            reference_type=OrderType.SELL_ORDER,
                            reference_id=so.id,
                        ),
                    )

                case ("SENT", "CANCELLED"):
                    self.inventory_service.adjust_quantity_allocated(
                        workspace_id,
                        line.item_id,
                        -line.quantity,
                    )

                case _:
                    pass

    def create_sell_order(self, workspace_id: UUID, data: SellOrderCreate) -> SellOrder:
        """Creates a SO and its nested lines in a single atomic transaction."""
        self._check_so_unique(workspace_id, data.so_number)

        so_data = data.model_dump(exclude={"sell_order_lines"})
        lines_data = data.sell_order_lines

        sell_order = SellOrder(workspace_id=workspace_id, **so_data)

        total_amount = 0
        for line_data in lines_data:
            line = SellOrderLine(**line_data.model_dump())
            total_amount += line.quantity * line.unit_cost
            sell_order.sell_order_lines.append(line)

        sell_order.total_amount = total_amount

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

        # Total Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        # Pagination & Eager Loading
        skip = (page - 1) * limit
        sell_orders_query = base_query.options(selectinload(SellOrder.sell_order_lines)).offset(skip).limit(limit)
        sell_orders = list(self.db.execute(sell_orders_query).scalars().all())

        return SellOrderPaginatedResponse(items=sell_orders, total=total)

    def get_sell_order(self, workspace_id: UUID, sell_order_id: UUID) -> SellOrder:
        return self._get_active_sell_order(workspace_id, sell_order_id)

    def update_sell_order(self, workspace_id: UUID, sell_order_id: UUID, data: SellOrderUpdate) -> SellOrder:
        """Applies partial updates to SO metadata (Header only)."""
        sell_order = self._get_active_sell_order(workspace_id, sell_order_id)
        update_data = data.model_dump(exclude_unset=True)

        if "so_number" in update_data and update_data["so_number"] != sell_order.so_number:
            self._check_so_unique(workspace_id, update_data["so_number"], exclude_sell_order_id=sell_order_id)

        old_status = sell_order.status
        new_status = update_data.get("status", old_status)

        if old_status != new_status:
            self._handle_status_transition(workspace_id, sell_order, old_status, new_status)

        for key, value in update_data.items():
            setattr(sell_order, key, value)

        self.db.add(sell_order)
        self.db.commit()
        self.db.refresh(sell_order)
        return sell_order

    def delete_sell_order(self, workspace_id: UUID, sell_order_id: UUID) -> None:
        """
        Soft-deletes a SO and cascades the soft-delete to its lines.
        """
        sell_order = self._get_active_sell_order(workspace_id, sell_order_id)

        for line in sell_order.sell_order_lines:
            line.soft_delete()

        sell_order.soft_delete()
        self.db.commit()


class SellOrderLineService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory_service = InventoryService(db)

    def _ensure_so_is_editable(self, so: SellOrder) -> None:
        if so.status in ["RECEIVED", "CANCELLED"]:
            raise ValueError(f"Cannot modify lines on a {so.status} sell order.")  # noqa

    def _get_parent_so(self, workspace_id: UUID, sell_order_id: UUID) -> SellOrder:
        """Validates that the SO exists and belongs to the workspace before modifying lines."""
        stmt = select(SellOrder).where(
            SellOrder.workspace_id == workspace_id,
            SellOrder.id == sell_order_id,
            SellOrder.is_deleted.is_(False),
        )
        so = self.db.execute(stmt).scalar_one_or_none()
        if not so:
            raise SellOrderNotFoundError()
        return so

    def _get_line(self, sell_order_id: UUID, line_id: UUID) -> SellOrderLine:
        """Fetches a specific line belonging to a specific SO."""
        stmt = select(SellOrderLine).where(
            SellOrderLine.id == line_id,
            SellOrderLine.sell_order_id == sell_order_id,
            SellOrderLine.is_deleted.is_(False),
        )
        line = self.db.execute(stmt).scalar_one_or_none()
        if not line:
            raise SellOrderLineNotFoundError()
        return line

    def _recalculate_so_total(self, sell_order_id: UUID) -> None:
        """Recalculates the SO total directly from the database lines."""
        total_stmt = select(func.coalesce(func.sum(SellOrderLine.quantity * SellOrderLine.unit_cost), 0)).where(
            SellOrderLine.sell_order_id == sell_order_id
        )

        new_total = self.db.execute(total_stmt).scalar_one()

        so_stmt = select(SellOrder).where(SellOrder.id == sell_order_id)
        so = self.db.execute(so_stmt).scalar_one()
        so.total_amount = new_total
        self.db.add(so)

    def add_line(self, workspace_id: UUID, sell_order_id: UUID, data: SellOrderLineCreate) -> SellOrderLine:
        """Adds a line and updates the SO total."""
        so = self._get_parent_so(workspace_id, sell_order_id)
        self._ensure_so_is_editable(so)

        new_line = SellOrderLine(sell_order_id=sell_order_id, **data.model_dump())
        self.db.add(new_line)
        self.db.flush()

        if so.status == "SENT" and new_line.item_id:
            self.inventory_service.adjust_quantity_allocated(workspace_id, new_line.item_id, new_line.quantity)

        self._recalculate_so_total(sell_order_id)
        self.db.commit()
        self.db.refresh(new_line)
        return new_line

    def update_line(
        self, workspace_id: UUID, sell_order_id: UUID, line_id: UUID, data: SellOrderLineUpdate
    ) -> SellOrderLine:
        """Updates a line and mathematically recalculates the SO total."""
        so = self._get_parent_so(workspace_id, sell_order_id)
        self._ensure_so_is_editable(so)

        line = self._get_line(sell_order_id, line_id)
        update_data = data.model_dump(exclude_unset=True)

        if so.status == "SENT" and "quantity" in update_data and line.item_id:
            delta = update_data["quantity"] - line.quantity
            self.inventory_service.adjust_quantity_allocated(workspace_id, line.item_id, delta)

        for key, value in update_data.items():
            setattr(line, key, value)

        self.db.add(line)
        self.db.flush()

        if "quantity" in update_data or "unit_cost" in update_data:
            self._recalculate_so_total(sell_order_id)

        self.db.commit()
        self.db.refresh(line)
        return line

    def remove_line(self, workspace_id: UUID, sell_order_id: UUID, line_id: UUID) -> None:
        """Removes a line and updates the SO total amount."""
        so = self._get_parent_so(workspace_id, sell_order_id)
        self._ensure_so_is_editable(so)

        line = self._get_line(sell_order_id, line_id)

        if so.status == "CONFIRMED" and line.item_id:
            self.inventory_service.adjust_quantity_allocated(workspace_id, line.item_id, -line.quantity)

        if line in so.sell_order_lines:
            so.sell_order_lines.remove(line)

        self.db.delete(line)
        self.db.flush()

        self._recalculate_so_total(sell_order_id)
        self.db.commit()
