from enum import Enum
from typing import ClassVar

from sqlalchemy import Select, or_, select

from erp.api.modules.bin.models import Bin
from erp.api.modules.inventory.models import Inventory
from erp.api.modules.item.models import Item
from erp.core.filter import BaseFilter, FilterSpec


class DeletedFilterEnum(Enum):
    ACTIVE = False
    DELETED = True


class BinFilter(BaseFilter):
    is_deleted: bool | None = None

    __filter_config__: ClassVar[dict[str, FilterSpec]] = {
        "is_deleted": FilterSpec(
            column_name="is_deleted",
            operator="eq",
            label="Status",
            placeholder="All Bins",
            enum_type=DeletedFilterEnum,
        ),
    }

    def apply_search(self, query: Select, search: str | None) -> Select:
        if not search:
            return query

        search_term = f"%{search}%"

        item_match = (
            select(Inventory.id)
            .join(Item, Item.id == Inventory.item_id)
            .where(
                Inventory.bin_id == Bin.id,
                Inventory.workspace_id == Bin.workspace_id,
                Inventory.is_deleted.is_(False),
                Item.is_deleted.is_(False),
                or_(
                    Item.sku.ilike(search_term),
                    Item.title.ilike(search_term),
                ),
            )
            .exists()
        )

        return query.where(
            or_(
                Bin.code.ilike(search_term),
                Bin.zone.ilike(search_term),
                item_match,
            )
        )
