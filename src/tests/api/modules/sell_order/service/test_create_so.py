import pytest

from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.exceptions import SellOrderExistsError
from erp.api.modules.sell_order.schemas import SellOrderCreate, SellOrderLineCreate
from erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_create_sell_order_success(db_session, seed_workspace, active_customer, event_bus):
    service = SellOrderService(db_session, event_bus)
    payload = SellOrderCreate(
        so_number="SO-100",
        customer_id=active_customer.id,
        status=SOStatusEnum.DRAFT,
        sell_order_lines=[
            SellOrderLineCreate(quantity=2, unit_cost=500),
            SellOrderLineCreate(quantity=3, unit_cost=100),
        ],
    )

    so = await service.create_sell_order(seed_workspace, payload)
    assert so.id is not None
    assert so.so_number == "SO-100"
    assert so.total_amount == 1300
    assert so.workspace_id == seed_workspace
    assert len(so.sell_order_lines) == 2


@pytest.mark.asyncio
async def test_create_sell_order_duplicate_number_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    payload = SellOrderCreate(so_number="SO-DUP", status=SOStatusEnum.DRAFT, sell_order_lines=[])

    await service.create_sell_order(seed_workspace, payload)

    with pytest.raises(SellOrderExistsError):
        await service.create_sell_order(seed_workspace, payload)


@pytest.mark.asyncio
async def test_create_sell_order_cross_tenant_number_allowed(db_session, seed_workspace, alt_workspace, event_bus):
    """Ensures two separate workspaces can use the same sell order number."""
    service = SellOrderService(db_session, event_bus)
    payload = SellOrderCreate(so_number="SO-SHARED", status=SOStatusEnum.DRAFT, sell_order_lines=[])

    await service.create_sell_order(seed_workspace, payload)
    cross_so = await service.create_sell_order(alt_workspace, payload)

    assert cross_so.workspace_id == alt_workspace
    assert cross_so.so_number == "SO-SHARED"
