from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.erp.api.base.service import BaseService
from src.erp.api.modules.inventory.exceptions import InsufficientInventoryError
from src.erp.api.modules.inventory.models import Inventory, StockMovement
from src.erp.api.modules.inventory.schemas.inventory import (
    InventoryPaginatedResponse,
)
from src.erp.api.modules.inventory.schemas.stock_movement import (
    StockMovementCreate,
    StockMovementPaginatedResponse,
)


class InventoryService(BaseService[Inventory]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Inventory)

    def _get_or_create_inventory(self, workspace_id: UUID, item_id: UUID, lock_for_update: bool = False) -> Inventory:
        """
        Helper method to securely fetch an item's inventory.
        If it doesn't exist, it initialises it at 0.
        Only locks the row with FOR UPDATE if lock_for_update is True.
        """
        base_stmt = select(Inventory).where(Inventory.workspace_id == workspace_id, Inventory.item_id == item_id)

        stmt = base_stmt.with_for_update() if lock_for_update else base_stmt

        inventory = self.db.execute(stmt).scalar_one_or_none()

        if not inventory:
            try:
                with self.db.begin_nested():
                    inventory = Inventory(
                        workspace_id=workspace_id,
                        item_id=item_id,
                        quantity_on_hand=0,
                        quantity_allocated=0,
                        quantity_on_order=0,
                    )
                    self.db.add(inventory)
                    self.db.flush()
            except IntegrityError:
                retry_stmt = base_stmt.with_for_update() if lock_for_update else base_stmt
                inventory = self.db.execute(retry_stmt).scalar_one()

        return inventory

    def get_inventories(
        self,
        workspace_id: UUID,
        page: int = 1,
        limit: int = 20,
        expand: list[str] | None = None,
    ) -> InventoryPaginatedResponse:
        """Fetches paginated inventory balances and the total count."""

        base_query = select(Inventory).where(
            Inventory.workspace_id == workspace_id,
            Inventory.is_deleted.is_(False),
        )

        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        loader_options = self.build_loader_options(expand)

        items_query = (
            base_query.options(*loader_options)
            .order_by(Inventory.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        items = list(self.db.execute(items_query).scalars().unique().all())

        return InventoryPaginatedResponse(
            items=items,
            total=total,
        )

    def get_inventory_by_item(self, workspace_id: UUID, item_id: UUID) -> Inventory:
        """Fetches a single inventory balance by item_id (no lock)."""
        return self._get_or_create_inventory(workspace_id, item_id, lock_for_update=False)

    def create_stock_movement(self, workspace_id: UUID, data: StockMovementCreate) -> StockMovement:
        """
        Creates a stock movement and automatically updates the ON-HAND inventory.
        Locks the inventory row during update and commits the transaction.
        """
        inventory = self._get_or_create_inventory(workspace_id, data.item_id, lock_for_update=True)

        if inventory.quantity_on_hand + data.quantity_change < 0:
            raise InsufficientInventoryError()

        inventory.quantity_on_hand += data.quantity_change

        movement = StockMovement(
            workspace_id=workspace_id,
            **data.model_dump(),
        )

        self.db.add(movement)
        self.db.add(inventory)

        self.db.flush()
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
        if delta == 0:
            return

        inventory = self._get_or_create_inventory(workspace_id, item_id, lock_for_update=True)

        if inventory.quantity_on_order + delta < 0:
            raise InsufficientInventoryError()

        inventory.quantity_on_order += delta
        self.db.add(inventory)

    def adjust_quantity_allocated(self, workspace_id: UUID, item_id: UUID, delta: int) -> None:
        if delta == 0:
            return

        inventory = self._get_or_create_inventory(workspace_id, item_id, lock_for_update=True)

        # 1. Prevent negative allocation when decreasing (delta < 0)
        if inventory.quantity_allocated + delta < 0:
            raise InsufficientInventoryError()

        # 2. Prevent over-allocation when increasing (delta > 0)
        if delta > 0:
            available_stock = inventory.quantity_on_hand - inventory.quantity_allocated
            if available_stock < delta:
                raise InsufficientInventoryError()

        inventory.quantity_allocated += delta
        self.db.add(inventory)
