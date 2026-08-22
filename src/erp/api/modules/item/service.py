from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.item.exceptions import ItemExistsError, ItemNotFoundError
from src.erp.api.modules.item.models import Item
from src.erp.api.modules.item.schemas import ItemCreate, ItemPaginatedResponse, ItemUpdate


class ItemService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory_service = InventoryService(db)

    def _get_active_item(self, workspace_id: UUID, item_id: UUID) -> Item:
        """Securely fetch an item enforcing workspace isolation."""
        stmt = select(Item).where(
            Item.workspace_id == workspace_id,
            Item.id == item_id,
            Item.is_deleted.is_(False),
        )
        item = self.db.execute(stmt).scalar_one_or_none()

        if not item:
            raise ItemNotFoundError()
        return item

    def _check_sku_unique(self, workspace_id: UUID, sku: str, exclude_item_id: UUID | None = None) -> None:
        """Ensures SKU is unique within the workspace."""
        stmt = select(Item).where(Item.workspace_id == workspace_id, Item.sku == sku, Item.is_deleted.is_(False))

        if exclude_item_id:
            stmt = stmt.where(Item.id != exclude_item_id)

        if self.db.execute(stmt).scalar_one_or_none():
            raise ItemExistsError()

    def create_item(self, workspace_id: UUID, data: ItemCreate) -> Item:
        """Creates an item and initialises its inventory record atomically."""
        self._check_sku_unique(workspace_id, data.sku)

        item = Item(
            workspace_id=workspace_id,
            **data.model_dump(),
        )

        self.db.add(item)
        self.db.flush()

        self.inventory_service.get_inventory_by_item(
            workspace_id=workspace_id,
            item_id=item.id,
        )

        self.db.commit()
        self.db.refresh(item)

        return item

    def get_items(
        self, workspace_id: UUID, search: str | None = None, page: int = 1, limit: int = 20
    ) -> ItemPaginatedResponse:
        """Fetches paginated items and the total count."""
        base_query = select(Item).where(
            Item.workspace_id == workspace_id,
            Item.is_deleted.is_(False),
        )

        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Item.title.ilike(search_term),
                    Item.sku.ilike(search_term),
                )
            )

        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_query).scalar_one()

        skip = (page - 1) * limit
        items_query = (
            base_query.order_by(
                Item.created_at.desc(),
                Item.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.execute(items_query).scalars().all())

        return ItemPaginatedResponse(items=items, total=total)

    def get_item(self, workspace_id: UUID, item_id: UUID) -> Item:
        """Fetches a single active item."""
        return self._get_active_item(workspace_id, item_id)

    def update_item(self, workspace_id: UUID, item_id: UUID, data: ItemUpdate) -> Item:
        """Applies partial updates, validating uniqueness if the SKU changes."""
        item = self._get_active_item(workspace_id, item_id)
        update_data = data.model_dump(exclude_unset=True)

        if "sku" in update_data and update_data["sku"] != item.sku:
            self._check_sku_unique(workspace_id, update_data["sku"], exclude_item_id=item_id)

        for key, value in update_data.items():
            setattr(item, key, value)

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_item(self, workspace_id: UUID, item_id: UUID) -> None:
        """Soft-deletes an item."""
        item = self._get_active_item(workspace_id, item_id)
        item.soft_delete()
        self.db.commit()
