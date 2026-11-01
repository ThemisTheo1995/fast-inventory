from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.base.service import BaseService
from erp.api.modules.inventory.enums import StockMovementType
from erp.api.modules.inventory.exceptions import (
    InsufficientInventoryError,
    InventoryNotFoundError,
    PickPackInvalidQuantityError,
    TransferStockSameBinError,
)
from erp.api.modules.inventory.filters.inventory import InventoryFilter
from erp.api.modules.inventory.models import Inventory, StockMovement
from erp.api.modules.inventory.schemas.inventory import InventoryPaginatedResponse, InventoryResponse
from erp.api.modules.inventory.schemas.inventory_expanded import (
    InventoryExpandedPaginatedResponse,
    InventoryExpandedResponse,
)
from erp.api.modules.inventory.schemas.stock_movement import (
    StockMovementCreate,
    StockMovementPaginatedResponse,
)
from erp.api.modules.inventory.schemas.transfer import InventoryTransferRequest
from erp.api.modules.item.models import Item
from erp.api.modules.item.service import ItemService


class InventoryService(BaseService[Inventory]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Inventory)

    async def _get_or_create_inventory(
        self, workspace_id: UUID, item_id: UUID, bin_id: UUID, lock_for_update: bool = False
    ) -> Inventory:
        """Fetch an inventory record for a specific item and bin within a workspace, creating it if it doesn't exist."""
        base_stmt = select(Inventory).where(
            Inventory.workspace_id == workspace_id,
            Inventory.item_id == item_id,
            Inventory.bin_id == bin_id,
        )

        stmt = base_stmt.with_for_update() if lock_for_update else base_stmt

        result = await self.db.execute(stmt)
        inventory = result.scalar_one_or_none()

        if not inventory:
            try:
                async with self.db.begin_nested():
                    inventory = Inventory(
                        workspace_id=workspace_id,
                        item_id=item_id,
                        bin_id=bin_id,
                        quantity_on_hand=0,
                    )
                    self.db.add(inventory)
                    await self.db.flush()
            except IntegrityError:
                retry_stmt = base_stmt.with_for_update() if lock_for_update else base_stmt
                result = await self.db.execute(retry_stmt)
                inventory = result.scalar_one()

        return inventory

    async def _get_inventory(
        self, workspace_id: UUID, inventory_id: UUID, expand: list[str] | None = None
    ) -> Inventory:
        """Fetch a specific inventory record by its ID within a workspace."""
        base_stmt = select(Inventory).where(
            Inventory.workspace_id == workspace_id, Inventory.id == inventory_id, Inventory.is_deleted.is_(False)
        )

        if expand:
            loader_options = self.build_loader_options(expand)
            base_stmt = base_stmt.options(*loader_options)

        result = await self.db.execute(base_stmt)
        inventory = result.unique().scalar_one_or_none()

        if not inventory:
            raise InventoryNotFoundError()

        return inventory

    async def get_inventories(
        self,
        workspace_id: UUID,
        filters: InventoryFilter | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
        expand: list[str] | None = None,
    ) -> InventoryPaginatedResponse | InventoryExpandedPaginatedResponse:
        """Fetch a paginated list of inventory records within a workspace, applying filters, search, and expansion."""

        filters = filters or InventoryFilter()

        base_query = select(Inventory).where(Inventory.workspace_id == workspace_id, Inventory.is_deleted.is_(False))

        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Item.title.ilike(search_term),
                    Item.sku.ilike(search_term),
                )
            )

        base_query = filters.apply(base_query, Inventory)

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        loader_options = self.build_loader_options(expand)

        skip = (page - 1) * limit
        items_query = (
            base_query.options(*loader_options)
            .order_by(Inventory.created_at.desc(), Inventory.id.desc())
            .offset(skip)
            .limit(limit)
        )

        items_result = await self.db.execute(items_query)
        items = list(items_result.scalars().unique().all())

        table_filters = await filters.build_ui_filters(self.db, workspace_id)

        if expand:
            return InventoryExpandedPaginatedResponse(items=items, total=total, filters=table_filters)

        return InventoryPaginatedResponse(items=items, total=total, filters=table_filters)

    async def get_inventory(self, workspace_id: UUID, inventory_id: UUID, expand: list[str] | None = None) -> Inventory:
        """Fetch a single inventory record by its ID within a workspace."""

        inventory = await self._get_inventory(workspace_id, inventory_id, expand=expand)

        if expand:
            return InventoryExpandedResponse.model_validate(inventory)

        return InventoryResponse.model_validate(inventory)

    async def get_inventory_by_item(self, workspace_id: UUID, item_id: UUID, bin_id: UUID) -> Inventory:
        """Fetches a single inventory balance by item_id and bin_id (no lock)."""
        return await self._get_or_create_inventory(workspace_id, item_id, bin_id=bin_id, lock_for_update=False)

    # STOCK MOVEMENT METHODS

    async def create_stock_movement(self, workspace_id: UUID, data: StockMovementCreate) -> StockMovement:
        """
        Creates a stock movement and automatically updates the ON-HAND inventory in the specific bin.
        Locks the inventory row during update and commits the transaction.
        """

        inventory = await self._get_or_create_inventory(
            workspace_id, data.item_id, bin_id=data.bin_id, lock_for_update=True
        )

        if inventory.quantity_on_hand + data.quantity_change < 0:
            raise InsufficientInventoryError()

        inventory.quantity_on_hand += data.quantity_change

        movement = StockMovement(
            workspace_id=workspace_id,
            **data.model_dump(),
        )

        self.db.add(movement)
        self.db.add(inventory)

        await self.db.flush()
        await self.db.refresh(movement)

        return movement

    async def get_stock_movements(
        self,
        workspace_id: UUID,
        item_id: UUID | None = None,
        bin_id: UUID | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> StockMovementPaginatedResponse:
        """Fetches paginated stock movements, optionally filtered by item_id & bin_id."""
        base_query = select(StockMovement).where(
            StockMovement.workspace_id == workspace_id,
            StockMovement.is_deleted.is_(False),
        )

        if item_id:
            base_query = base_query.where(StockMovement.item_id == item_id)
        if bin_id:
            base_query = base_query.where(StockMovement.bin_id == bin_id)

        base_query = base_query.order_by(StockMovement.created_at.desc())

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        skip = (page - 1) * limit
        items_query = base_query.offset(skip).limit(limit)
        items_result = await self.db.execute(items_query)
        items = list(items_result.scalars().all())

        return StockMovementPaginatedResponse(items=items, total=total)


class InventoryTransferService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.inventory_service = InventoryService(db)

    async def bin_to_bin_transfer(
        self, workspace_id: UUID, data: InventoryTransferRequest
    ) -> tuple[StockMovement | None, StockMovement | None]:

        if data.source_bin_id == data.destination_bin_id:
            raise TransferStockSameBinError()

        source = await self.inventory_service._get_or_create_inventory(
            workspace_id,
            data.item_id,
            bin_id=data.source_bin_id,
            lock_for_update=True,
        )

        destination = await self.inventory_service._get_or_create_inventory(
            workspace_id,
            data.item_id,
            bin_id=data.destination_bin_id,
            lock_for_update=True,
        )

        if data.quantity > source.quantity_on_hand:
            raise InsufficientInventoryError()

        if data.quantity == source.quantity_on_hand:
            return await self._execute_full_transfer_keep_empty(workspace_id, data, source, destination)

        return await self._execute_partial_transfer(workspace_id, data, source, destination)

    async def _execute_full_transfer_keep_empty(
        self, workspace_id: UUID, data: InventoryTransferRequest, source: Inventory, destination: Inventory
    ) -> tuple[StockMovement, StockMovement]:
        """Transfer all physical stock, keeping source bin active with 0 quantity."""
        transfer_qty = source.quantity_on_hand

        destination.quantity_on_hand += transfer_qty
        source.quantity_on_hand = 0

        out_movement, in_movement = self._build_movements(
            workspace_id, data, source.bin_id, destination.bin_id, transfer_qty, action_label="Transfer"
        )

        self.db.add(source)
        self.db.add(destination)
        self.db.add(out_movement)
        self.db.add(in_movement)

        await self.db.commit()
        await self.db.refresh(out_movement)
        await self.db.refresh(in_movement)

        return out_movement, in_movement

    async def _execute_partial_transfer(
        self, workspace_id: UUID, data: InventoryTransferRequest, source: Inventory, destination: Inventory
    ) -> tuple[StockMovement, StockMovement]:
        """Transfer a subset of physical stock between bins."""
        transfer_qty = data.quantity

        source.quantity_on_hand -= transfer_qty
        destination.quantity_on_hand += transfer_qty

        out_movement, in_movement = self._build_movements(
            workspace_id, data, source.bin_id, destination.bin_id, transfer_qty, action_label="Transfer"
        )

        self.db.add(source)
        self.db.add(destination)
        self.db.add(out_movement)
        self.db.add(in_movement)

        await self.db.commit()
        await self.db.refresh(out_movement)
        await self.db.refresh(in_movement)

        return out_movement, in_movement

    def _build_movements(
        self,
        workspace_id: UUID,
        data: InventoryTransferRequest,
        source_bin_id: UUID,
        destination_bin_id: UUID,
        transfer_qty: int,
        action_label: str,
    ) -> tuple[StockMovement, StockMovement]:
        notes_text = f"{action_label} from bin {source_bin_id} to bin {destination_bin_id}"

        if data.notes and data.notes.strip():
            notes_text += f"\n\n{data.notes.strip()}"

        out_movement = StockMovement(
            workspace_id=workspace_id,
            item_id=data.item_id,
            bin_id=source_bin_id,
            quantity_change=-transfer_qty,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
            notes=f"OUT: {notes_text}",
        )

        in_movement = StockMovement(
            workspace_id=workspace_id,
            item_id=data.item_id,
            bin_id=destination_bin_id,
            quantity_change=transfer_qty,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
            notes=f"IN: {notes_text}",
        )

        return out_movement, in_movement


class PickPackService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.inventory_service = InventoryService(db)
        self.item_service = ItemService(db)

    async def pickpack_sell_order_line(
        self,
        workspace_id: UUID,
        sell_order_id: UUID,
        item_id: UUID,
        bin_id: UUID,
        quantity_to_fulfill: int,
    ) -> StockMovement:
        """Executes physical pickpacking for a sell order line."""
        if quantity_to_fulfill <= 0:
            msg = "Fulfillment quantity must be greater than zero."
            raise PickPackInvalidQuantityError(detail=msg)

        inventory = await self.inventory_service._get_or_create_inventory(
            workspace_id, item_id, bin_id=bin_id, lock_for_update=True
        )

        if inventory.quantity_on_hand < quantity_to_fulfill:
            raise InsufficientInventoryError()

        inventory.quantity_on_hand -= quantity_to_fulfill
        self.db.add(inventory)

        movement = StockMovement(
            workspace_id=workspace_id,
            item_id=item_id,
            bin_id=bin_id,
            quantity_change=-quantity_to_fulfill,
            reference_type=StockMovementType.SELL_ORDER,
            reference_id=sell_order_id,
            notes=f"Fulfilled {quantity_to_fulfill} units for Sell Order {sell_order_id} from bin {bin_id}",
        )
        self.db.add(movement)

        await self.db.flush()
        await self.db.refresh(movement)

        return movement

    async def pickpack_purchase_order_line(
        self,
        workspace_id: UUID,
        purchase_order_id: UUID,
        item_id: UUID,
        bin_id: UUID,
        quantity_received: int,
    ) -> StockMovement:
        """Executes physical pickpacking for a purchase order line."""
        if quantity_received <= 0:
            msg = "Received quantity must be greater than zero."
            raise PickPackInvalidQuantityError(detail=msg)

        inventory = await self.inventory_service._get_or_create_inventory(
            workspace_id, item_id, bin_id=bin_id, lock_for_update=True
        )

        inventory.quantity_on_hand += quantity_received
        self.db.add(inventory)

        movement = StockMovement(
            workspace_id=workspace_id,
            item_id=item_id,
            bin_id=bin_id,
            quantity_change=quantity_received,
            reference_type=StockMovementType.PURCHASE_ORDER,
            reference_id=purchase_order_id,
            notes=f"Received {quantity_received} units for Purchase Order {purchase_order_id} into bin {bin_id}",
        )
        self.db.add(movement)

        await self.db.flush()
        await self.db.refresh(movement)
        return movement
