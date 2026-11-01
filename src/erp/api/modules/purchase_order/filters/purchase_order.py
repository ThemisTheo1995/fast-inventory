from typing import ClassVar
from uuid import UUID

from pydantic import Field
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.item.models import Item
from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine
from erp.core.filter import BaseFilter, FilterSpec
from erp.core.utils import get_amount_slider_range


async def get_po_amount_range(
    db: AsyncSession,
    workspace_id: UUID,
) -> tuple[float, float, float]:
    result = (
        await db.execute(
            select(
                func.min(PurchaseOrder.total_amount),
                func.max(PurchaseOrder.total_amount),
            ).where(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.is_deleted.is_(False),
            )
        )
    ).first()

    if not result or result[0] is None:
        return 0, 10000, 500

    return get_amount_slider_range(*result)


class PurchaseOrderFilter(BaseFilter):
    search: str | None = Field(
        default=None,
        description="Search by PO number, item title or item SKU",
    )
    status: POStatusEnum | None = Field(
        default=None,
        description="Filter by PO status",
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
            enum_type=POStatusEnum,
        ),
        "total_amount": FilterSpec(
            column_name="total_amount",
            operator="between",
            type="range",
            label="Amount",
            placeholder="Amount Range",
            range_fn=get_po_amount_range,
            step=None,
            prefix="£",
        ),
    }

    def apply(self, query: Select, model: type) -> Select:
        query = super().apply(query, model)

        if self.search:
            search_term = f"%{self.search.strip()}%"

            query = query.where(
                or_(
                    PurchaseOrder.po_number.ilike(search_term),
                    PurchaseOrder.purchase_order_lines.any(
                        PurchaseOrderLine.item.has(
                            or_(
                                Item.title.ilike(search_term),
                                Item.sku.ilike(search_term),
                            )
                        )
                    ),
                )
            )

        return query
