import pytest

from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.filters.purchase_order import PurchaseOrderFilter
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_get_purchase_orders_pagination_and_search(
    db_session,
    seed_workspace,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    # Arrange
    await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="APPLE-1",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[],
        ),
    )
    await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="APPLE-2",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[],
        ),
    )
    await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="BANANA-1",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[],
        ),
    )

    # Pagination
    page_one = await service.get_purchase_orders(
        seed_workspace,
        page=1,
        limit=2,
    )

    assert len(page_one.items) == 2
    assert page_one.total == 3

    page_two = await service.get_purchase_orders(
        seed_workspace,
        page=2,
        limit=2,
    )

    assert len(page_two.items) == 1
    assert page_two.total == 3

    page_one_numbers = {po.po_number for po in page_one.items}
    page_two_numbers = {po.po_number for po in page_two.items}

    assert page_one_numbers.isdisjoint(page_two_numbers)

    # Search through PurchaseOrderFilter
    search_res = await service.get_purchase_orders(
        seed_workspace,
        filters=PurchaseOrderFilter(search="APPLE"),
    )

    assert search_res.total == 2
    assert len(search_res.items) == 2
    assert {po.po_number for po in search_res.items} == {
        "APPLE-1",
        "APPLE-2",
    }
