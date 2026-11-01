import uuid

import pytest

from erp.api.modules.inventory.enums import StockMovementType
from erp.api.modules.inventory.exceptions import (
    InsufficientInventoryError,
    PickPackInvalidQuantityError,
)
from erp.api.modules.inventory.schemas.stock_movement import StockMovementCreate
from erp.api.modules.inventory.service import InventoryService, PickPackService


@pytest.mark.asyncio
async def test_pickpack_sell_order_line_success(db_session, seed_workspace, active_item, seed_bin):
    inventory_service = InventoryService(db_session)
    pickpack_service = PickPackService(db_session)
    sell_order_id = uuid.uuid4()

    await inventory_service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_change=20,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    movement = await pickpack_service.pickpack_sell_order_line(
        workspace_id=seed_workspace,
        sell_order_id=sell_order_id,
        item_id=active_item.id,
        bin_id=seed_bin.id,
        quantity_to_fulfill=5,
    )

    inventory = await inventory_service.get_inventory_by_item(seed_workspace, active_item.id, seed_bin.id)

    assert movement.quantity_change == -5
    assert movement.reference_type == StockMovementType.SELL_ORDER
    assert movement.reference_id == sell_order_id
    assert movement.bin_id == seed_bin.id
    assert inventory.quantity_on_hand == 15


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", [0, -1])
async def test_pickpack_sell_order_line_invalid_quantity(db_session, seed_workspace, active_item, seed_bin, quantity):
    pickpack_service = PickPackService(db_session)

    with pytest.raises(PickPackInvalidQuantityError):
        await pickpack_service.pickpack_sell_order_line(
            workspace_id=seed_workspace,
            sell_order_id=uuid.uuid4(),
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_to_fulfill=quantity,
        )


@pytest.mark.asyncio
async def test_pickpack_sell_order_line_insufficient_stock(db_session, seed_workspace, active_item, seed_bin):
    pickpack_service = PickPackService(db_session)

    with pytest.raises(InsufficientInventoryError):
        await pickpack_service.pickpack_sell_order_line(
            workspace_id=seed_workspace,
            sell_order_id=uuid.uuid4(),
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_to_fulfill=5,
        )


@pytest.mark.asyncio
async def test_pickpack_purchase_order_line_success(db_session, seed_workspace, active_item, seed_bin):
    inventory_service = InventoryService(db_session)
    pickpack_service = PickPackService(db_session)
    purchase_order_id = uuid.uuid4()

    movement = await pickpack_service.pickpack_purchase_order_line(
        workspace_id=seed_workspace,
        purchase_order_id=purchase_order_id,
        item_id=active_item.id,
        bin_id=seed_bin.id,
        quantity_received=12,
    )

    inventory = await inventory_service.get_inventory_by_item(seed_workspace, active_item.id, seed_bin.id)

    assert movement.quantity_change == 12
    assert movement.reference_type == StockMovementType.PURCHASE_ORDER
    assert movement.reference_id == purchase_order_id
    assert movement.bin_id == seed_bin.id
    assert inventory.quantity_on_hand == 12


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", [0, -1])
async def test_pickpack_purchase_order_line_invalid_quantity(
    db_session, seed_workspace, active_item, seed_bin, quantity
):
    pickpack_service = PickPackService(db_session)

    with pytest.raises(PickPackInvalidQuantityError):
        await pickpack_service.pickpack_purchase_order_line(
            workspace_id=seed_workspace,
            purchase_order_id=uuid.uuid4(),
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_received=quantity,
        )
