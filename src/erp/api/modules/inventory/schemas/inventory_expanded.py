from pydantic import BaseModel

from erp.api.modules.bin.schemas.bin import BinResponse
from erp.api.modules.inventory.schemas.inventory import InventoryResponse
from erp.api.modules.item.schemas import ItemResponse
from erp.core.filter import TableFilter


class InventoryExpandedResponse(InventoryResponse):
    item: ItemResponse | None = None
    bin: BinResponse | None = None


class InventoryExpandedPaginatedResponse(BaseModel):
    """Payload for paginated expanded inventory lists."""

    items: list[InventoryExpandedResponse]
    total: int
    filters: list[TableFilter] = []
