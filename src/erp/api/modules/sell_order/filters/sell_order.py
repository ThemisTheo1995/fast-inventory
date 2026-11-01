from typing import ClassVar
from uuid import UUID

from pydantic import Field
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.item.models import Item
from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.models import SellOrder, SellOrderLine
from erp.core.filter import BaseFilter, FilterSpec
from erp.core.utils import get_amount_slider_range


async def get_so_amount_range(
    db: AsyncSession,
    workspace_id: UUID,
) -> tuple[float, float, float]:
    """Get the dynamic amount slider range for active SOs in a workspace."""
    result = (
        await db.execute(
            select(
                func.min(SellOrder.total_amount),
                func.max(SellOrder.total_amount),
            ).where(
                SellOrder.workspace_id == workspace_id,
                SellOrder.is_deleted.is_(False),
            )
        )
    ).first()

    if not result or result[0] is None:
        return 0, 10000, 500

    return get_amount_slider_range(*result)


class SellOrderFilter(BaseFilter):
    search: str | None = Field(
        default=None,
        description="Search by SO number, item title or item SKU",
    )
    status: SOStatusEnum | None = Field(
        default=None,
        description="Filter by SO status",
    )
    total_amount: str | None = Field(
        default=None,
        description="Range as 'min,max'",
    )

    __filter_config__: ClassVar[dict[str, FilterSpec]] = {
        "status": FilterSpec(
            column_name="status",
            operator="eq",
            label="Status",
            placeholder="All Statuses",
            enum_type=SOStatusEnum,
        ),
        "total_amount": FilterSpec(
            column_name="total_amount",
            operator="between",
            type="range",
            label="Amount",
            placeholder="Amount Range",
            range_fn=get_so_amount_range,
            step=None,
            prefix="£",
        ),
    }

    def apply(self, query: Select, model: type) -> Select:
        query = super().apply(query, model)

        if self.search and self.search.strip():
            search_term = f"%{self.search.strip()}%"

            query = query.where(
                or_(
                    SellOrder.so_number.ilike(search_term),
                    SellOrder.sell_order_lines.any(
                        SellOrderLine.item.has(
                            or_(
                                Item.title.ilike(search_term),
                                Item.sku.ilike(search_term),
                            )
                        )
                    ),
                )
            )

        return query
