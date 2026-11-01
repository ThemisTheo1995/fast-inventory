import pytest
from sqlalchemy import select

from erp.api.modules.inventory.models import Inventory
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
async def test_update_sell_order_basic_metadata(
    db_session,
    seed_workspace,
    active_sell_order,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    updated = await service.update_sell_order(
        seed_workspace,
        active_sell_order.id,
        SellOrderUpdate(so_number="SO-NEW-NUM"),
    )

    assert updated.so_number == "SO-NEW-NUM"


@pytest.mark.asyncio
async def test_update_sell_order_duplicate_number_fails(
    db_session,
    seed_workspace,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    so1 = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(so_number="SO-ONE", sell_order_lines=[]),
    )

    await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(so_number="SO-TWO", sell_order_lines=[]),
    )

    with pytest.raises(SellOrderExistsError):
        await service.update_sell_order(
            seed_workspace,
            so1.id,
            SellOrderUpdate(so_number="SO-TWO"),
        )


@pytest.mark.asyncio
async def test_update_sell_order_same_number_allowed(
    db_session,
    seed_workspace,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(so_number="SO-SAME", sell_order_lines=[]),
    )

    updated = await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(so_number="SO-SAME"),
    )

    assert updated.so_number == "SO-SAME"


@pytest.mark.asyncio
async def test_status_transition_draft_to_confirmed_allocates_item_quantity(
    db_session,
    seed_workspace,
    event_bus,
    stocked_item,
):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-1",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=stocked_item.id,
                    quantity=10,
                    unit_cost=50,
                ),
            ],
        ),
    )

    await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(status=SOStatusEnum.CONFIRMED),
    )

    allocated = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == stocked_item.id,
        )
    )

    assert allocated == 10


@pytest.mark.asyncio
async def test_status_transition_confirmed_to_fulfilled_releases_allocation(
    db_session,
    seed_workspace,
    event_bus,
    stocked_item,
):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-2",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=stocked_item.id,
                    quantity=5,
                    unit_cost=50,
                ),
            ],
        ),
    )

    await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(status=SOStatusEnum.CONFIRMED),
    )

    await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(status=SOStatusEnum.FULLFILLED),
    )

    allocated = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == stocked_item.id,
        )
    )

    physical_stock = await db_session.scalar(
        select(Inventory.quantity_on_hand).where(
            Inventory.item_id == stocked_item.id,
        )
    )

    assert allocated == 0

    # Fulfilment currently only releases allocation.
    # It does not create a stock movement or reduce physical stock.
    assert physical_stock == 100


@pytest.mark.asyncio
async def test_status_transition_confirmed_to_cancelled_releases_allocation(
    db_session,
    seed_workspace,
    event_bus,
    stocked_item,
):
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-3",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=stocked_item.id,
                    quantity=7,
                    unit_cost=100,
                ),
            ],
        ),
    )

    await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(status=SOStatusEnum.CONFIRMED),
    )

    await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(status=SOStatusEnum.CANCELLED),
    )

    allocated = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == stocked_item.id,
        )
    )

    assert allocated == 0


@pytest.mark.asyncio
async def test_status_transition_fulfilled_to_returned_does_not_change_stock(
    db_session,
    seed_workspace,
    event_bus,
    stocked_item,
):
    """The current returned handler is a no-op."""
    service = SellOrderService(db_session, event_bus)

    so = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-RET-1",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[
                SellOrderLineCreate(
                    item_id=stocked_item.id,
                    quantity=10,
                    unit_cost=50,
                ),
            ],
        ),
    )

    await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(status=SOStatusEnum.CONFIRMED),
    )

    await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(status=SOStatusEnum.FULLFILLED),
    )

    await service.update_sell_order(
        seed_workspace,
        so.id,
        SellOrderUpdate(status=SOStatusEnum.RETURNED),
    )

    allocated = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == stocked_item.id,
        )
    )

    physical_stock = await db_session.scalar(
        select(Inventory.quantity_on_hand).where(
            Inventory.item_id == stocked_item.id,
        )
    )

    assert allocated == 0
    assert physical_stock == 100


@pytest.mark.asyncio
async def test_status_transition_invalid_paths_fail(
    db_session,
    seed_workspace,
    event_bus,
):
    service = SellOrderService(db_session, event_bus)

    so_cancelled = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-ERR-1",
            status=SOStatusEnum.CANCELLED,
            sell_order_lines=[],
        ),
    )

    so_returned = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-ERR-2",
            status=SOStatusEnum.RETURNED,
            sell_order_lines=[],
        ),
    )

    so_fulfilled = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-ERR-3",
            status=SOStatusEnum.FULLFILLED,
            sell_order_lines=[],
        ),
    )

    so_draft = await service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-ERR-4",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[],
        ),
    )

    with pytest.raises(SellOrderStatusTerminalError):
        await service.update_sell_order(
            seed_workspace,
            so_cancelled.id,
            SellOrderUpdate(status=SOStatusEnum.CONFIRMED),
        )

    with pytest.raises(SellOrderStatusTerminalError):
        await service.update_sell_order(
            seed_workspace,
            so_returned.id,
            SellOrderUpdate(status=SOStatusEnum.DRAFT),
        )

    with pytest.raises(SellOrderStatusTransitionError):
        await service.update_sell_order(
            seed_workspace,
            so_fulfilled.id,
            SellOrderUpdate(status=SOStatusEnum.DRAFT),
        )

    with pytest.raises(SellOrderStatusTransitionError):
        await service.update_sell_order(
            seed_workspace,
            so_draft.id,
            SellOrderUpdate(status=SOStatusEnum.RETURNED),
        )
