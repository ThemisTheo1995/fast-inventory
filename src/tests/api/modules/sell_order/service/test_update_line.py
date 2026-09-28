import uuid

import pytest

from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.item.models import Item
from src.erp.api.modules.sell_order.enums import SOStatusEnum
from src.erp.api.modules.sell_order.exceptions import (
    SellOrderLineItemChangeError,
    SellOrderLineNotFoundError,
    SellOrderNotEditableError,
)
from src.erp.api.modules.sell_order.schemas import (
    SellOrderCreate,
    SellOrderLineCreate,
    SellOrderLineUpdate,
)
from src.erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_update_line_recalculates_total_and_inventory(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-5", title="I5", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-3",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=10, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    # Simulate manual initial adjustment since creation bypasses transition logic
    await inv_service.adjust_quantity_allocated(seed_workspace, item.id, 10)
    await db_session.flush()

    await service.update_line(
        seed_workspace,
        so.id,
        line_id,
        SellOrderLineUpdate(quantity=15, unit_cost=20),
    )

    updated_so = await service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 300

    inv_updated = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 15


@pytest.mark.asyncio
async def test_update_line_on_uneditable_so_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-UPD-UNEDITABLE",
            status=SOStatusEnum.FULLFILLED,
            sell_order_lines=[SellOrderLineCreate(quantity=1, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderNotEditableError):
        await service.update_line(seed_workspace, so.id, line_id, SellOrderLineUpdate(quantity=5, unit_cost=10))


@pytest.mark.asyncio
async def test_get_active_line_not_found(db_session, event_bus):
    """Verifies that _get_active_line raises an error when the line does not exist."""
    service = SellOrderService(db_session, event_bus)

    with pytest.raises(SellOrderLineNotFoundError):
        await service._get_active_line(sell_order_id=uuid.uuid4(), line_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_update_line_not_found_fails(db_session, seed_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    fake_id = uuid.uuid4()

    with pytest.raises(SellOrderLineNotFoundError):
        await service.update_line(
            seed_workspace, active_sell_order.id, fake_id, SellOrderLineUpdate(quantity=5, unit_cost=10)
        )


@pytest.mark.asyncio
async def test_update_line_item_id_change_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    item1 = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-7", title="I7", base_price=10, is_deleted=False)
    item2 = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-8", title="I8", base_price=20, is_deleted=False)
    db_session.add_all([item1, item2])
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-6",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item1.id, quantity=1, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderLineItemChangeError):
        await service.update_line(
            seed_workspace, so.id, line_id, SellOrderLineUpdate(item_id=item2.id, quantity=1, unit_cost=50)
        )


@pytest.mark.asyncio
async def test_update_line_same_quantity_no_inventory_change(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-9", title="I9", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-DELTA-0",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=10, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    await inv_service.adjust_quantity_allocated(seed_workspace, item.id, 10)
    await db_session.flush()

    await service.update_line(
        seed_workspace, so.id, line_id, SellOrderLineUpdate(item_id=item.id, quantity=10, unit_cost=25)
    )

    updated_so = await service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 250

    inv_updated = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 10  # Unchanged


@pytest.mark.asyncio
async def test_update_line_without_item_id_bypasses_events(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-NO-ITEM-UPD",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=None, quantity=1, unit_cost=50)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    await service.update_line(
        seed_workspace, so.id, line_id, SellOrderLineUpdate(item_id=None, quantity=5, unit_cost=50)
    )
    updated_so = await service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 250
