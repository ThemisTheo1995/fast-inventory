from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderExistsError,
    PurchaseOrderLineNotFoundError,
    PurchaseOrderNotFoundError,
)
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine
from src.erp.api.modules.purchase_order.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineUpdate,
    PurchaseOrderPaginatedResponse,
    PurchaseOrderUpdate,
)


class PurchaseOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_active_purchase_order(self, workspace_id: UUID, purchase_order_id: UUID) -> PurchaseOrder:
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
        purchase_order = self.db.execute(stmt).scalar_one_or_none()

        if not purchase_order:
            raise PurchaseOrderNotFoundError()
        return purchase_order

    def _check_po_unique(
        self, workspace_id: UUID, po_number: str, exclude_purchase_order_id: UUID | None = None
    ) -> None:
        """Ensures PO number is unique within the workspace."""
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.workspace_id == workspace_id, PurchaseOrder.po_number == po_number
        )

        if exclude_purchase_order_id:
            stmt = stmt.where(PurchaseOrder.id != exclude_purchase_order_id)

        if self.db.execute(stmt).scalar_one_or_none():
            raise PurchaseOrderExistsError()

    def create_purchase_order(self, workspace_id: UUID, data: PurchaseOrderCreate) -> PurchaseOrder:
        """Creates a PO and its nested lines in a single atomic transaction."""
        self._check_po_unique(workspace_id, data.po_number)

        # Extract PO header data vs Line data
        po_data = data.model_dump(exclude={"purchase_order_lines"})
        lines_data = data.purchase_order_lines

        purchase_order = PurchaseOrder(workspace_id=workspace_id, **po_data)

        total_amount = 0
        for line_data in lines_data:
            line = PurchaseOrderLine(**line_data.model_dump())
            total_amount += line.quantity * line.unit_cost
            purchase_order.purchase_order_lines.append(line)

        purchase_order.total_amount = total_amount

        self.db.add(purchase_order)
        self.db.commit()
        self.db.refresh(purchase_order)

        return purchase_order

    def get_purchase_orders(
        self, workspace_id: UUID, search: str | None = None, page: int = 1, limit: int = 20
    ) -> PurchaseOrderPaginatedResponse:
        """Fetches paginated POs with lines eager-loaded."""
        base_query = select(PurchaseOrder).where(
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrder.is_deleted.is_(False),
        )

        if search:
            base_query = base_query.where(PurchaseOrder.po_number.ilike(f"%{search}%"))

        # Total Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        # Pagination & Eager Loading
        skip = (page - 1) * limit
        purchase_orders_query = (
            base_query.options(selectinload(PurchaseOrder.purchase_order_lines)).offset(skip).limit(limit)
        )
        purchase_orders = list(self.db.execute(purchase_orders_query).scalars().all())

        return PurchaseOrderPaginatedResponse(items=purchase_orders, total=total)

    def get_purchase_order(self, workspace_id: UUID, purchase_order_id: UUID) -> PurchaseOrder:
        return self._get_active_purchase_order(workspace_id, purchase_order_id)

    def update_purchase_order(
        self, workspace_id: UUID, purchase_order_id: UUID, data: PurchaseOrderUpdate
    ) -> PurchaseOrder:
        """Applies partial updates to PO metadata (Header only)."""
        purchase_order = self._get_active_purchase_order(workspace_id, purchase_order_id)
        update_data = data.model_dump(exclude_unset=True)

        if "po_number" in update_data and update_data["po_number"] != purchase_order.po_number:
            self._check_po_unique(workspace_id, update_data["po_number"], exclude_purchase_order_id=purchase_order_id)

        for key, value in update_data.items():
            setattr(purchase_order, key, value)

        self.db.add(purchase_order)
        self.db.commit()
        self.db.refresh(purchase_order)
        return purchase_order

    def delete_purchase_order(self, workspace_id: UUID, purchase_order_id: UUID) -> None:
        """
        Soft-deletes a PO and cascades the soft-delete to its lines.
        """
        purchase_order = self._get_active_purchase_order(workspace_id, purchase_order_id)

        for line in purchase_order.purchase_order_lines:
            line.soft_delete()

        purchase_order.soft_delete()
        self.db.commit()


class PurchaseOrderLineService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_parent_po(self, workspace_id: UUID, purchase_order_id: UUID) -> PurchaseOrder:
        """Validates that the PO exists and belongs to the workspace before modifying lines."""
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.workspace_id == workspace_id,
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.is_deleted.is_(False),
        )
        po = self.db.execute(stmt).scalar_one_or_none()
        if not po:
            raise PurchaseOrderNotFoundError()
        return po

    def _get_line(self, purchase_order_id: UUID, line_id: UUID) -> PurchaseOrderLine:
        """Fetches a specific line belonging to a specific PO."""
        stmt = select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == line_id,
            PurchaseOrderLine.purchase_order_id == purchase_order_id,
            PurchaseOrderLine.is_deleted.is_(False),
        )
        line = self.db.execute(stmt).scalar_one_or_none()
        if not line:
            raise PurchaseOrderLineNotFoundError()
        return line

    def _recalculate_po_total(self, purchase_order_id: UUID) -> None:
        """Recalculates the PO total directly from the database lines."""
        total_stmt = select(func.coalesce(func.sum(PurchaseOrderLine.quantity * PurchaseOrderLine.unit_cost), 0)).where(
            PurchaseOrderLine.purchase_order_id == purchase_order_id
        )

        new_total = self.db.execute(total_stmt).scalar_one()

        po_stmt = select(PurchaseOrder).where(PurchaseOrder.id == purchase_order_id)
        po = self.db.execute(po_stmt).scalar_one()
        po.total_amount = new_total
        self.db.add(po)

    def add_line(self, workspace_id: UUID, purchase_order_id: UUID, data: PurchaseOrderLineCreate) -> PurchaseOrderLine:
        """Adds a line and updates the PO total."""
        self._get_parent_po(workspace_id, purchase_order_id)

        new_line = PurchaseOrderLine(purchase_order_id=purchase_order_id, **data.model_dump())
        self.db.add(new_line)
        self.db.flush()

        self._recalculate_po_total(purchase_order_id)
        self.db.commit()
        self.db.refresh(new_line)
        return new_line

    def update_line(
        self, workspace_id: UUID, purchase_order_id: UUID, line_id: UUID, data: PurchaseOrderLineUpdate
    ) -> PurchaseOrderLine:
        """Updates a line and mathematically recalculates the PO total."""
        self._get_parent_po(workspace_id, purchase_order_id)
        line = self._get_line(purchase_order_id, line_id)

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(line, key, value)

        self.db.add(line)
        self.db.flush()

        if "quantity" in update_data or "unit_cost" in update_data:
            self._recalculate_po_total(purchase_order_id)

        self.db.commit()
        self.db.refresh(line)
        return line

    def remove_line(self, workspace_id: UUID, purchase_order_id: UUID, line_id: UUID) -> None:
        """Removes a line and updates the PO total amount."""
        self._get_parent_po(workspace_id, purchase_order_id)
        line = self._get_line(purchase_order_id, line_id)

        self.db.delete(line)
        self.db.flush()

        self._recalculate_po_total(purchase_order_id)
        self.db.commit()
