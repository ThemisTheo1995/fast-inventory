import uuid

import pytest

from erp.api.modules.inventory.service import InventoryService
from erp.api.modules.item.models import Item
from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.exceptions import SellOrderNotEditableError
from erp.api.modules.sell_order.schemas import SellOrderCreate, SellOrderLineCreate
from erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_add_line_recalculates_total(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(so_number="SO-LINE-1", status=SOStatusEnum.DRAFT, sell_order_lines=[]),
    )

    await service.add_line(seed_workspace, so.id, SellOrderLineCreate(item_id=None, quantity=10, unit_cost=15))

    updated_so = await service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 150


@pytest.mark.asyncio
async def test_add_line_to_confirmed_order_allocates_inventory(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-4", title="I4", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 10
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-LINE-2", status=SOStatusEnum.CONFIRMED, sell_order_lines=[])
    )

    await service.add_line(seed_workspace, so.id, SellOrderLineCreate(item_id=item.id, quantity=4, unit_cost=10))

    inv_updated = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 4


@pytest.mark.asyncio
async def test_add_line_on_uneditable_so_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-ADD-UNEDITABLE",
            status=SOStatusEnum.FULLFILLED,
            sell_order_lines=[SellOrderLineCreate(quantity=1, unit_cost=10)],
        ),
    )

    with pytest.raises(SellOrderNotEditableError):
        await service.add_line(seed_workspace, so.id, SellOrderLineCreate(quantity=1, unit_cost=10))
