import uuid

import pytest
from sqlalchemy import select

from erp.api.modules.item.models import Item
from erp.api.modules.item.service import ItemService
from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.exceptions import (
    SellOrderLineNotFoundError,
    SellOrderNotEditableError,
)
from erp.api.modules.sell_order.schemas import SellOrderCreate, SellOrderLineCreate
from erp.api.modules.sell_order.service import SellOrderService


@pytest.mark.asyncio
async def test_remove_line_recalculates_total_and_deallocates(
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
            so_number="SO-LINE-4",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=stocked_item.id,
                    quantity=8,
                    unit_cost=10,
                ),
                SellOrderLineCreate(
                    item_id=stocked_item.id,
                    quantity=2,
                    unit_cost=10,
                ),
            ],
        ),
    )

    line_id_to_delete = so.sell_order_lines[0].id

    # Creating an order directly as CONFIRMED does not publish a
    # confirmation event, so establish its initial allocation.
    await item_service.adjust_quantity_allocated(
        seed_workspace,
        stocked_item.id,
        10,
    )

    await service.remove_line(
        seed_workspace,
        so.id,
        line_id_to_delete,
    )

    updated_so = await service.get_sell_order(seed_workspace, so.id)

    allocated = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == stocked_item.id,
        )
    )

    assert updated_so.total_amount == 20
    assert len(updated_so.sell_order_lines) == 1
    assert allocated == 2


@pytest.mark.asyncio
async def test_remove_line_on_uneditable_so_fails(
    db_session,
    seed_workspace,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-REM-UNEDITABLE",
            status=SOStatusEnum.FULLFILLED,
            sell_order_lines=[
                SellOrderLineCreate(quantity=1, unit_cost=10),
            ],
        ),
    )

    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderNotEditableError):
        await service.remove_line(seed_workspace, so.id, line_id)


@pytest.mark.asyncio
async def test_remove_line_not_found_fails(
    db_session,
    seed_workspace,
    active_sell_order,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    with pytest.raises(SellOrderLineNotFoundError):
        await service.remove_line(
            seed_workspace,
            active_sell_order.id,
            uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_remove_line_without_item_id_bypasses_allocation_event(
    db_session,
    seed_workspace,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-NO-ITEM-REM",
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

    await service.remove_line(seed_workspace, so.id, line_id)

    final_so = await service.get_sell_order(seed_workspace, so.id)

    assert final_so.total_amount == 0
    assert final_so.sell_order_lines == []
