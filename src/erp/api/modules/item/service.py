from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.api.modules.inventory.exceptions import InsufficientInventoryError
from erp.api.modules.item.exceptions import ItemExistsError, ItemNotFoundError
from erp.api.modules.item.filters.item import ItemFilter
from erp.api.modules.item.models import Item
from erp.api.modules.item.schemas import ItemBarcode, ItemCreate, ItemPaginatedResponse, ItemUpdate
from erp.services.barcode.events import send_barcode_generation_event


class ItemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _generate_barcode_id(workspace_id: UUID, sku: str) -> str:
        """Constructs the unique barcode identifier."""
        return f"{workspace_id}_{sku}"

    async def _get_active_item(
        self,
        workspace_id: UUID,
        item_id: UUID,
        include_deleted: bool = False,
        lock_for_update: bool = False,
    ) -> Item:
        conditions = [Item.workspace_id == workspace_id, Item.id == item_id]

        if not include_deleted:
            conditions.append(Item.is_deleted.is_(False))

        stmt = (
            select(Item)
            .options(selectinload(Item.inventory_items))
            .where(*conditions)
            .execution_options(populate_existing=True)
        )

        if lock_for_update:
            stmt = stmt.with_for_update()

        result = await self.db.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            raise ItemNotFoundError()

        return item

    async def _check_sku_unique(
        self,
        workspace_id: UUID,
        sku: str,
        exclude_item_id: UUID | None = None,
    ) -> None:
        stmt = select(Item).where(Item.workspace_id == workspace_id, Item.sku == sku)

        if exclude_item_id is not None:
            stmt = stmt.where(Item.id != exclude_item_id)

        result = await self.db.execute(stmt)

        if result.scalar_one_or_none():
            raise ItemExistsError()

    async def create_item(self, workspace_id: UUID, data: ItemCreate) -> Item:
        """Creates an item and generates its barcode_id (no bin inventory created until stock arrives)."""
        await self._check_sku_unique(workspace_id, data.sku)

        barcode_id = self._generate_barcode_id(workspace_id, data.sku)

        item = Item(
            workspace_id=workspace_id,
            barcode_id=barcode_id,
            **data.model_dump(),
        )

        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)

        send_barcode_generation_event(
            ItemBarcode(
                barcode_id=item.barcode_id,
                workspace_id=workspace_id,
            )
        )

        return item

    async def get_items(
        self,
        workspace_id: UUID,
        filters: ItemFilter | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> ItemPaginatedResponse:
        """Fetches paginated items and the total count."""
        if filters is None:
            filters = ItemFilter()

        if filters.is_deleted is None:
            filters = filters.model_copy(update={"is_deleted": False})

        base_query = select(Item).where(
            Item.workspace_id == workspace_id,
        )

        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Item.title.ilike(search_term),
                    Item.sku.ilike(search_term),
                )
            )

        base_query = filters.apply(base_query, Item)

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        skip = (page - 1) * limit
        items_query = (
            base_query.options(selectinload(Item.inventory_items))
            .order_by(
                Item.is_deleted.asc(),
                Item.created_at.desc(),
                Item.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )

        items_result = await self.db.execute(items_query)
        items = list(items_result.scalars().all())

        table_filters = await filters.build_ui_filters(self.db, workspace_id)

        return ItemPaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            filters=table_filters,
        )

    async def get_item(self, workspace_id: UUID, item_id: UUID) -> Item:
        """Fetches a single active item."""
        return await self._get_active_item(workspace_id, item_id)

    async def update_item(self, workspace_id: UUID, item_id: UUID, data: ItemUpdate) -> Item:
        """Applies partial updates, validating uniqueness if the SKU changes."""
        update_data = data.model_dump(exclude_unset=True)
        include_deleted = "is_deleted" in update_data

        item = await self._get_active_item(workspace_id, item_id, include_deleted=include_deleted)

        sku_changed = "sku" in update_data and update_data["sku"] != item.sku

        if sku_changed:
            new_sku = update_data["sku"]
            await self._check_sku_unique(workspace_id, new_sku, exclude_item_id=item_id)
            update_data["barcode_id"] = self._generate_barcode_id(workspace_id, new_sku)

        for key, value in update_data.items():
            setattr(item, key, value)

        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)

        if sku_changed and item.barcode_id:
            send_barcode_generation_event(
                ItemBarcode(
                    barcode_id=item.barcode_id,
                    workspace_id=workspace_id,
                )
            )

        return item

    async def delete_item(self, workspace_id: UUID, item_id: UUID) -> None:
        """Soft-deletes an item."""
        item = await self._get_active_item(workspace_id, item_id)
        item.soft_delete()
        await self.db.commit()

    async def adjust_quantity_on_order(self, workspace_id: UUID, item_id: UUID, delta: int) -> None:
        """Adjusts global incoming purchase order quantity for an item."""
        if delta == 0:
            return

        item = await self._get_active_item(workspace_id, item_id)
        if item.quantity_on_order + delta < 0:
            raise InsufficientInventoryError()

        item.quantity_on_order += delta
        await self.db.flush()

    async def adjust_quantity_allocated(self, workspace_id: UUID, item_id: UUID, delta: int) -> None:
        """Adjusts global sell order allocation for an item, verifying available physical stock across bins."""
        if delta == 0:
            return

        item = await self._get_active_item(workspace_id, item_id, lock_for_update=True)

        if item.quantity_allocated + delta < 0:
            raise InsufficientInventoryError()

        if delta > 0 and (item.total_quantity_on_hand - item.quantity_allocated) < delta:
            raise InsufficientInventoryError()

        item.quantity_allocated += delta
        await self.db.flush()
