from enum import Enum
from typing import ClassVar

from src.erp.core.filter import BaseFilter, FilterSpec


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
        ),
    }
