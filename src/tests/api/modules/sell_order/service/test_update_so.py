import uuid

import pytest

from erp.api.modules.inventory.enums import OrderType
from erp.api.modules.inventory.service import InventoryService
from erp.api.modules.item.models import Item
from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.exceptions import (
    SellOrderExistsError,
    SellOrderStatusTerminalError,
    SellOrderStatusTransitionError,
)
from erp.api.modules.sell_order.schemas import (
    SellOrderCreate,
    SellOrderLineCreate,
    SellOrderUpdate,
)
from erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_update_sell_order_basic_metadata(db_session, seed_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    update_payload = SellOrderUpdate(so_number="SO-NEW-NUM")

    updated = await service.update_sell_order(seed_workspace, active_sell_order.id, update_payload)
    assert updated.so_number == "SO-NEW-NUM"


@pytest.mark.asyncio
async def test_update_sell_order_duplicate_number_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    so1 = await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ONE", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )
    await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-TWO", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    with pytest.raises(SellOrderExistsError):
        await service.update_sell_order(seed_workspace, so1.id, SellOrderUpdate(so_number="SO-TWO"))


@pytest.mark.asyncio
async def test_update_sell_order_same_number_allowed(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    so = await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-SAME", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    updated = await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(so_number="SO-SAME"))
    assert updated.so_number == "SO-SAME"


@pytest.mark.asyncio
async def test_status_transition_draft_to_confirmed_allocates_inventory(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-1", title="I1", base_price=10, is_deleted=False)
    db_session.add(item)
    await db_session.flush()

    # Provide enough stock to allocate
    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 100
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-1",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=10, unit_cost=50)],
        ),
    )

    await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_allocated == 10


@pytest.mark.asyncio
async def test_status_transition_confirmed_to_fulfilled_creates_stock_movement(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-2", title="I2", base_price=10, is_deleted=False)
    db_session.add(item)
    await db_session.flush()

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-2",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=5, unit_cost=50)],
        ),
    )

    await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))
    await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.FULLFILLED))

    inv_updated = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 0
    assert inv_updated.quantity_on_hand == 45

    movements = await inv_service.get_stock_movements(seed_workspace, item_id=item.id)
    assert movements.items[0].quantity_change == -5
    assert movements.items[0].reference_type == OrderType.SELL_ORDER


@pytest.mark.asyncio
async def test_status_transition_confirmed_to_cancelled_clears_allocation(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-3", title="I3", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 100
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-3",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=7, unit_cost=100)],
        ),
    )

    await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))
    await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CANCELLED))

    inv_updated = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 0


@pytest.mark.asyncio
async def test_status_transition_fulfilled_to_returned_restores_stock(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-RET", title="RET", base_price=10, is_deleted=False
    )
    db_session.add(item)

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-RET-1",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=10, unit_cost=50)],
        ),
    )

    await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))
    await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.FULLFILLED))
    await service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.RETURNED))

    inv_updated = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_on_hand == 50  # 50 - 10 (fulfilled) + 10 (returned)


@pytest.mark.asyncio
async def test_status_transition_invalid_paths_fail(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so_can = await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ERR-1", status=SOStatusEnum.CANCELLED, sell_order_lines=[])
    )
    so_ret = await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ERR-2", status=SOStatusEnum.RETURNED, sell_order_lines=[])
    )
    so_ful = await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ERR-3", status=SOStatusEnum.FULLFILLED, sell_order_lines=[])
    )
    so_draft = await service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ERR-4", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    # From Terminal states (TerminalError)
    with pytest.raises(SellOrderStatusTerminalError):
        await service.update_sell_order(seed_workspace, so_can.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))

    with pytest.raises(SellOrderStatusTerminalError):
        await service.update_sell_order(seed_workspace, so_ret.id, SellOrderUpdate(status=SOStatusEnum.DRAFT))

    # From Fulfilled to anything but Returned (TransitionError)
    with pytest.raises(SellOrderStatusTransitionError):
        await service.update_sell_order(seed_workspace, so_ful.id, SellOrderUpdate(status=SOStatusEnum.DRAFT))

    # Invalid path not in TRANSITION_EVENTS dictionary (Draft -> Returned)
    with pytest.raises(SellOrderStatusTransitionError):
        await service.update_sell_order(seed_workspace, so_draft.id, SellOrderUpdate(status=SOStatusEnum.RETURNED))
