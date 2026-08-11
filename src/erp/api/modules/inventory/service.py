from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.erp.api.modules.inventory.exceptions import InsufficientInventoryError
from src.erp.api.modules.inventory.models import Inventory, StockMovement
from src.erp.api.modules.inventory.schemas import (
    InventoryPaginatedResponse,
    StockMovementCreate,
    StockMovementPaginatedResponse,
)


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_or_create_inventory(self, workspace_id: UUID, item_id: UUID) -> Inventory:
        """
        Helper method to securely fetch an item's inventory.
        If it doesn't exist, it initialises it at 0.
        """
        stmt = (
            select(Inventory)
            .where(Inventory.workspace_id == workspace_id, Inventory.item_id == item_id)
            .with_for_update()
        )

        inventory = self.db.execute(stmt).scalar_one_or_none()

        if not inventory:
            inventory = Inventory(
                workspace_id=workspace_id,
                item_id=item_id,
                quantity_on_hand=0,
                quantity_allocated=0,
                quantity_on_order=0,
            )
            self.db.add(inventory)
            self.db.flush()

        return inventory

    def get_inventories(self, workspace_id: UUID, page: int = 1, limit: int = 20) -> InventoryPaginatedResponse:
        """Fetches paginated inventory balances and the total count."""
        base_query = select(Inventory).where(
            Inventory.workspace_id == workspace_id,
            Inventory.is_deleted.is_(False),
        )

        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        skip = (page - 1) * limit
        items_query = base_query.offset(skip).limit(limit)
        items = list(self.db.execute(items_query).scalars().all())

        return InventoryPaginatedResponse(items=items, total=total)

    def get_inventory_by_item(self, workspace_id: UUID, item_id: UUID) -> Inventory:
        """Fetches a single inventory balance by item_id."""
        return self._get_or_create_inventory(workspace_id, item_id)

    def create_stock_movement(self, workspace_id: UUID, data: StockMovementCreate) -> StockMovement:
        """
        Creates a stock movement and automatically updates the ON-HAND inventory.
        This ensures atomic ledger updates for physical stock.
        """
        inventory = self._get_or_create_inventory(workspace_id, data.item_id)

        if inventory.quantity_on_hand + data.quantity_change < 0:
            raise InsufficientInventoryError()

        inventory.quantity_on_hand += data.quantity_change

        movement = StockMovement(
            workspace_id=workspace_id,
            **data.model_dump(),
        )

        self.db.add(movement)
        self.db.add(inventory)

        self.db.commit()
        self.db.refresh(movement)

        return movement

    def get_stock_movements(
        self, workspace_id: UUID, item_id: UUID | None = None, page: int = 1, limit: int = 20
    ) -> StockMovementPaginatedResponse:
        """Fetches paginated stock movements, optionally filtered by item_id."""
        base_query = select(StockMovement).where(
            StockMovement.workspace_id == workspace_id,
            StockMovement.is_deleted.is_(False),
        )

        if item_id:
            base_query = base_query.where(StockMovement.item_id == item_id)

        # Order by newest first
        base_query = base_query.order_by(StockMovement.created_at.desc())

        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        skip = (page - 1) * limit
        items_query = base_query.offset(skip).limit(limit)
        items = list(self.db.execute(items_query).scalars().all())

        return StockMovementPaginatedResponse(items=items, total=total)

    def adjust_quantity_on_order(self, workspace_id: UUID, item_id: UUID, delta: int) -> None:
        """Adjusts the pending incoming stock. Does NOT create a stock movement."""
        if delta == 0:
            return
        inventory = self._get_or_create_inventory(workspace_id, item_id)
        inventory.quantity_on_order += delta
        self.db.add(inventory)

    def adjust_quantity_allocated(self, workspace_id: UUID, item_id: UUID, delta: int) -> None:
        """Adjusts the pending outgoing stock. Does NOT create a stock movement."""
        if delta == 0:
            return
        inventory = self._get_or_create_inventory(workspace_id, item_id)
        inventory.quantity_allocated += delta
        # Optional: Add a check here to raise InsufficientInventoryError if you
        # don't allow backorders (quantity_allocated > quantity_on_hand).
        self.db.add(inventory)
