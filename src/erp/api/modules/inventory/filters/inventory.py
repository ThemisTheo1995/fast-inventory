from enum import Enum
from typing import ClassVar

from sqlalchemy import Select, or_, select

from erp.api.modules.inventory.models import Inventory
from erp.api.modules.item.models import Item
from erp.core.filter import BaseFilter, FilterSpec


class DeletedFilterEnum(Enum):
    ACTIVE = False
    DELETED = True


class InventoryFilter(BaseFilter):
    is_deleted: bool | None = None

    __filter_config__: ClassVar[dict[str, FilterSpec]] = {
        "is_deleted": FilterSpec(
            column_name="is_deleted",
            operator="eq",
            type="select",
            enum_type=DeletedFilterEnum,
            label="Status",
            placeholder="Status",
            default_value=False,
        ),
    }

    def apply_search(self, query: Select, search: str | None) -> Select:
        if not search or not search.strip():
            return query

        search_term = f"%{search.strip()}%"

        item_match = (
            select(Item.id)
            .where(
                Item.id == Inventory.item_id,
                Item.is_deleted.is_(False),
                or_(
                    Item.sku.ilike(search_term),
                    Item.title.ilike(search_term),
                ),
            )
            .exists()
        )

        return query.where(item_match)
