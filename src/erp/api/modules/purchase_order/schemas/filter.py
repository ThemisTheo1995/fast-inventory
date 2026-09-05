import math
from typing import ClassVar
from uuid import UUID

from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.modules.purchase_order.enums import POStatusEnum
from src.erp.api.modules.purchase_order.models import PurchaseOrder
from src.erp.core.filter import BaseFilter, FilterSpec


async def get_po_amount_range(db: AsyncSession, workspace_id: UUID) -> tuple[int, int]:
    result = (
        await db.execute(
            select(func.min(PurchaseOrder.total_amount), func.max(PurchaseOrder.total_amount)).where(
                PurchaseOrder.workspace_id == workspace_id, PurchaseOrder.is_deleted.is_(False)
            )
        )
    ).first()

    if not result or result[0] is None:
        return (0, 10000)

    min_val, max_val = result[0], result[1]

    step = 2000
    clean_min = math.floor(min_val / step) * step
    clean_max = math.ceil(max_val / step) * step

    # Fallback to ensure there is an actual movable range
    if clean_min == clean_max:
        clean_max += step

    return (int(clean_min), int(clean_max))


class PurchaseOrderFilter(BaseFilter):
    status: POStatusEnum | None = Field(default=None, description="Filter by PO status")
    total_amount: str | None = Field(default=None, description="Range as 'min,max'")

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
            step=2000,
            prefix="£",
        ),
    }
