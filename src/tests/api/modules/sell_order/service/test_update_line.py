import uuid

import pytest
from sqlalchemy import select

from erp.api.modules.item.models import Item
from erp.api.modules.item.service import ItemService
from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.exceptions import (
    SellOrderLineItemChangeError,
    SellOrderLineNotFoundError,
    SellOrderNotEditableError,
)
from erp.api.modules.sell_order.schemas import (
    SellOrderCreate,
    SellOrderLineCreate,
    SellOrderLineUpdate,
)
from erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_update_line_recalculates_total_and_allocation(
    db_session,
    seed_workspace,
    event_bus,
    stocked_item,
):
    service = SellOrderService(db_session, event_bus)
    item_service = ItemService(db_session)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-3",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=stocked_item.id,
                    quantity=10,
                    unit_cost=10,
                ),
            ],
        ),
    )

    line_id = so.sell_order_lines[0].id

    # Establish the allocation already represented by this confirmed order.
    await item_service.adjust_quantity_allocated(
        seed_workspace,
        stocked_item.id,
        10,
    )

    await service.update_line(
        seed_workspace,
        so.id,
        line_id,
        SellOrderLineUpdate(
            quantity=15,
            unit_cost=20,
        ),
    )

    updated_so = await service.get_sell_order(seed_workspace, so.id)

    allocated = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == stocked_item.id,
        )
    )

    assert updated_so.total_amount == 300
    assert allocated == 15


@pytest.mark.asyncio
async def test_update_line_on_uneditable_so_fails(
    db_session,
    seed_workspace,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-UPD-UNEDITABLE",
            status=SOStatusEnum.FULLFILLED,
            sell_order_lines=[
                SellOrderLineCreate(quantity=1, unit_cost=10),
            ],
        ),
    )

    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderNotEditableError):
        await service.update_line(
            seed_workspace,
            so.id,
            line_id,
            SellOrderLineUpdate(quantity=5, unit_cost=10),
        )


@pytest.mark.asyncio
async def test_get_active_line_not_found(db_session, event_bus):
    service = SellOrderService(db_session, event_bus)

    with pytest.raises(SellOrderLineNotFoundError):
        await service._get_active_line(
            sell_order_id=uuid.uuid4(),
            line_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_update_line_not_found_fails(
    db_session,
    seed_workspace,
    active_sell_order,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    with pytest.raises(SellOrderLineNotFoundError):
        await service.update_line(
            seed_workspace,
            active_sell_order.id,
            uuid.uuid4(),
            SellOrderLineUpdate(quantity=5, unit_cost=10),
        )


@pytest.mark.asyncio
async def test_update_line_item_id_change_fails(
    db_session,
    seed_workspace,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    from erp.api.modules.item.models import Item

    item1 = Item(
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:8]}",
        title="Item 1",
        base_price=10,
        is_deleted=False,
    )
    item2 = Item(
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:8]}",
        title="Item 2",
        base_price=20,
        is_deleted=False,
    )

    db_session.add_all([item1, item2])
    await db_session.flush()

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-6",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=item1.id,
                    quantity=1,
                    unit_cost=10,
                ),
            ],
        ),
    )

    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderLineItemChangeError):
        await service.update_line(
            seed_workspace,
            so.id,
            line_id,
            SellOrderLineUpdate(
                item_id=item2.id,
                quantity=1,
                unit_cost=50,
            ),
        )


@pytest.mark.asyncio
async def test_update_line_same_quantity_does_not_change_allocation(
    db_session,
    seed_workspace,
    event_bus,
    stocked_item,
):
    service = SellOrderService(db_session, event_bus)
    item_service = ItemService(db_session)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-DELTA-0",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=stocked_item.id,
                    quantity=10,
                    unit_cost=10,
                ),
            ],
        ),
    )

    line_id = so.sell_order_lines[0].id

    await item_service.adjust_quantity_allocated(
        seed_workspace,
        stocked_item.id,
        10,
    )

    await service.update_line(
        seed_workspace,
        so.id,
        line_id,
        SellOrderLineUpdate(
            item_id=stocked_item.id,
            quantity=10,
            unit_cost=25,
        ),
    )

    updated_so = await service.get_sell_order(seed_workspace, so.id)

    allocated = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == stocked_item.id,
        )
    )

    assert updated_so.total_amount == 250
    assert allocated == 10


@pytest.mark.asyncio
async def test_update_line_without_item_id_bypasses_allocation_event(
    db_session,
    seed_workspace,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-NO-ITEM-UPD",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=None,
                    quantity=1,
                    unit_cost=50,
                ),
            ],
        ),
    )

    line_id = so.sell_order_lines[0].id

    await service.update_line(
        seed_workspace,
        so.id,
        line_id,
        SellOrderLineUpdate(
            item_id=None,
            quantity=5,
            unit_cost=50,
        ),
    )

    updated_so = await service.get_sell_order(seed_workspace, so.id)

    assert updated_so.total_amount == 250
    assert updated_so.sell_order_lines[0].quantity == 5
