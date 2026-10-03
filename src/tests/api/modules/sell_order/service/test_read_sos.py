import pytest

from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.schemas import SellOrderCreate
from erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_get_sell_orders_pagination_and_search(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="APPLE-1", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )
    await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="APPLE-2", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )
    await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="BANANA-1", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    res = await service.get_sell_orders(seed_workspace, page=1, limit=2)
    assert len(res.items) == 2
    assert res.total >= 3

    search_res = await service.get_sell_orders(seed_workspace, search="APPLE")
    assert len(search_res.items) == 2
