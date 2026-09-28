import uuid

import pytest

from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.item.models import Item
from src.erp.api.modules.sell_order.enums import SOStatusEnum
from src.erp.api.modules.sell_order.exceptions import (
    SellOrderLineNotFoundError,
    SellOrderNotEditableError,
)
from src.erp.api.modules.sell_order.schemas import SellOrderCreate, SellOrderLineCreate
from src.erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_remove_line_recalculates_total_and_deallocates(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-6", title="I6", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-4",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[
                SellOrderLineCreate(item_id=item.id, quantity=8, unit_cost=10),
                SellOrderLineCreate(item_id=item.id, quantity=2, unit_cost=10),
            ],
        ),
    )
    line_id_to_delete = so.sell_order_lines[0].id

    await inv_service.adjust_quantity_allocated(seed_workspace, item.id, 10)
    await db_session.flush()

    await service.remove_line(seed_workspace, so.id, line_id_to_delete)

    updated_so = await service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 20
    assert len(updated_so.sell_order_lines) == 1

    inv_updated = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 2


@pytest.mark.asyncio
async def test_remove_line_on_uneditable_so_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-REM-UNEDITABLE",
            status=SOStatusEnum.FULLFILLED,
            sell_order_lines=[SellOrderLineCreate(quantity=1, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderNotEditableError):
        await service.remove_line(seed_workspace, so.id, line_id)


@pytest.mark.asyncio
async def test_remove_line_not_found_fails(db_session, seed_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    fake_id = uuid.uuid4()

    with pytest.raises(SellOrderLineNotFoundError):
        await service.remove_line(seed_workspace, active_sell_order.id, fake_id)


@pytest.mark.asyncio
async def test_remove_line_without_item_id_bypasses_events(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-NO-ITEM-REM",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=None, quantity=1, unit_cost=50)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    await service.remove_line(seed_workspace, so.id, line_id)
    final_so = await service.get_sell_order(seed_workspace, so.id)
    assert final_so.total_amount == 0
