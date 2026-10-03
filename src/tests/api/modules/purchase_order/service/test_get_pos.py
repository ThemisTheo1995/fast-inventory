import pytest

from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_get_purchase_orders_pagination_and_search(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)

    await service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="APPLE-1", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )
    await service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="APPLE-2", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )
    await service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="BANANA-1", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )

    res = await service.get_purchase_orders(seed_workspace, page=1, limit=2)
    assert len(res.items) == 2
    assert res.total >= 3

    search_res = await service.get_purchase_orders(seed_workspace, search="APPLE")
    assert len(search_res.items) == 2
