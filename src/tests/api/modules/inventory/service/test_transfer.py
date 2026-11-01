import uuid

import pytest

from erp.api.modules.bin.models import Bin
from erp.api.modules.inventory.enums import StockMovementType
from erp.api.modules.inventory.exceptions import (
    InsufficientInventoryError,
    TransferStockSameBinError,
)
from erp.api.modules.inventory.schemas.stock_movement import StockMovementCreate
from erp.api.modules.inventory.schemas.transfer import InventoryTransferRequest
from erp.api.modules.inventory.service import InventoryService, InventoryTransferService


@pytest.fixture
async def destination_bin(db_session, seed_workspace):
    bin_obj = Bin(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        code=f"TRANSFER-{uuid.uuid4().hex[:8].upper()}",
        zone="Transfer Test Warehouse",
        is_deleted=False,
    )
    db_session.add(bin_obj)
    await db_session.commit()
    await db_session.refresh(bin_obj)
    return bin_obj


@pytest.mark.asyncio
async def test_bin_to_bin_full_transfer(db_session, seed_workspace, active_item, seed_bin, destination_bin):
    inventory_service = InventoryService(db_session)
    transfer_service = InventoryTransferService(db_session)

    await inventory_service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_change=20,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    data = InventoryTransferRequest(
        item_id=active_item.id,
        source_bin_id=seed_bin.id,
        destination_bin_id=destination_bin.id,
        quantity=20,
        notes="Full bin transfer",
    )

    out_movement, in_movement = await transfer_service.bin_to_bin_transfer(seed_workspace, data)

    source = await inventory_service.get_inventory_by_item(seed_workspace, active_item.id, seed_bin.id)
    destination = await inventory_service.get_inventory_by_item(seed_workspace, active_item.id, destination_bin.id)

    assert source.quantity_on_hand == 0
    assert destination.quantity_on_hand == 20
    assert out_movement.quantity_change == -20
    assert in_movement.quantity_change == 20
    assert out_movement.bin_id == seed_bin.id
    assert in_movement.bin_id == destination_bin.id
    assert "OUT:" in out_movement.notes
    assert "IN:" in in_movement.notes
    assert "Full bin transfer" in out_movement.notes


@pytest.mark.asyncio
async def test_bin_to_bin_partial_transfer(db_session, seed_workspace, active_item, seed_bin, destination_bin):
    inventory_service = InventoryService(db_session)
    transfer_service = InventoryTransferService(db_session)

    await inventory_service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_change=30,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    data = InventoryTransferRequest(
        item_id=active_item.id,
        source_bin_id=seed_bin.id,
        destination_bin_id=destination_bin.id,
        quantity=10,
    )

    out_movement, in_movement = await transfer_service.bin_to_bin_transfer(seed_workspace, data)

    source = await inventory_service.get_inventory_by_item(seed_workspace, active_item.id, seed_bin.id)
    destination = await inventory_service.get_inventory_by_item(seed_workspace, active_item.id, destination_bin.id)

    assert source.quantity_on_hand == 20
    assert destination.quantity_on_hand == 10
    assert out_movement.quantity_change == -10
    assert in_movement.quantity_change == 10


@pytest.mark.asyncio
async def test_bin_to_bin_transfer_same_bin_rejected(db_session, seed_workspace, active_item, seed_bin):
    transfer_service = InventoryTransferService(db_session)

    data = InventoryTransferRequest(
        item_id=active_item.id,
        source_bin_id=seed_bin.id,
        destination_bin_id=seed_bin.id,
        quantity=5,
    )

    with pytest.raises(TransferStockSameBinError):
        await transfer_service.bin_to_bin_transfer(seed_workspace, data)


@pytest.mark.asyncio
async def test_bin_to_bin_transfer_insufficient_stock(
    db_session, seed_workspace, active_item, seed_bin, destination_bin
):
    transfer_service = InventoryTransferService(db_session)

    data = InventoryTransferRequest(
        item_id=active_item.id,
        source_bin_id=seed_bin.id,
        destination_bin_id=destination_bin.id,
        quantity=5,
    )

    with pytest.raises(InsufficientInventoryError):
        await transfer_service.bin_to_bin_transfer(seed_workspace, data)
