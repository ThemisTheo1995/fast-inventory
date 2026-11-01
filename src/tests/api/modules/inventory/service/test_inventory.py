import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from erp.api.modules.bin.models import Bin
from erp.api.modules.inventory.enums import StockMovementType
from erp.api.modules.inventory.exceptions import InsufficientInventoryError, InventoryNotFoundError
from erp.api.modules.inventory.models import Inventory
from erp.api.modules.inventory.schemas.stock_movement import StockMovementCreate
from erp.api.modules.inventory.service import InventoryService

# ==============================================================================
# 1. CORE HELPER TESTS (_get_or_create_inventory)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_or_create_inventory_existing(db_session, seed_workspace, active_item, seed_bin):
    """Verifies it fetches the existing inventory for an item and bin."""
    service = InventoryService(db_session)

    inv = await service._get_or_create_inventory(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    assert inv.item_id == active_item.id
    assert inv.bin_id == seed_bin.id
    assert inv.quantity_on_hand == 0


@pytest.mark.asyncio
async def test_get_or_create_inventory_creates_new(db_session, seed_workspace, empty_item, seed_bin):
    """Verifies it creates a zero-quantity inventory record when missing."""
    service = InventoryService(db_session)

    inv = await service._get_or_create_inventory(
        seed_workspace,
        empty_item.id,
        bin_id=seed_bin.id,
    )

    assert inv.item_id == empty_item.id
    assert inv.workspace_id == seed_workspace
    assert inv.bin_id == seed_bin.id
    assert inv.quantity_on_hand == 0


@pytest.mark.asyncio
async def test_get_or_create_inventory_race_condition(db_session, seed_workspace, empty_item, seed_bin):
    """
    Verifies that if two requests attempt to create the same inventory
    record simultaneously, the IntegrityError is caught and the
    record created by the competing request is fetched.
    """
    service = InventoryService(db_session)

    original_execute = service.db.execute
    call_count = 0

    existing_inventory = Inventory(
        item_id=empty_item.id,
        workspace_id=seed_workspace,
        bin_id=seed_bin.id,
        quantity_on_hand=0,
    )

    async def fake_execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First lookup: inventory does not exist.
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            return mock_result

        if call_count == 2:
            # Retry after IntegrityError: another request created it.
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = existing_inventory
            return mock_result

        return await original_execute(stmt, *args, **kwargs)

    with (
        patch.object(service.db, "execute", side_effect=fake_execute),
        patch.object(
            service.db,
            "flush",
            new_callable=AsyncMock,
            side_effect=IntegrityError(None, None, BaseException()),
        ),
    ):
        inv = await service._get_or_create_inventory(
            seed_workspace,
            empty_item.id,
            bin_id=seed_bin.id,
            lock_for_update=True,
        )

    assert inv.item_id == empty_item.id
    assert inv.bin_id == seed_bin.id


# ==============================================================================
# 2. READ OPERATIONS
# ==============================================================================


@pytest.mark.asyncio
async def test_get_inventories_pagination_and_expand(db_session, seed_workspace, active_item, seed_bin):
    """Verifies fetching paginated inventory and expanding item relationships."""
    service = InventoryService(db_session)

    response = await service.get_inventories(
        seed_workspace,
        page=1,
        limit=10,
        expand=["item"],
    )

    assert response.total >= 1
    assert len(response.items) >= 1

    matching_inventory = next(
        inv for inv in response.items if inv.item_id == active_item.id and inv.bin_id == seed_bin.id
    )

    assert matching_inventory.item.sku == active_item.sku


@pytest.mark.asyncio
async def test_get_inventory_by_item(db_session, seed_workspace, active_item, seed_bin):
    """Verifies fetching inventory for a specific item and bin."""
    service = InventoryService(db_session)

    inv = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    assert inv.item_id == active_item.id
    assert inv.bin_id == seed_bin.id


@pytest.mark.asyncio
async def test_get_inventory_by_item_creates_missing_bin_balance(db_session, seed_workspace, empty_item, seed_bin):
    """Verifies that requesting a missing item/bin balance initializes it."""
    service = InventoryService(db_session)

    inv = await service.get_inventory_by_item(
        seed_workspace,
        empty_item.id,
        bin_id=seed_bin.id,
    )

    assert inv.item_id == empty_item.id
    assert inv.bin_id == seed_bin.id
    assert inv.quantity_on_hand == 0


# ==============================================================================
# 3. BIN-SPECIFIC INVENTORY
# ==============================================================================


@pytest.mark.asyncio
async def test_same_item_has_independent_inventory_per_bin(db_session, seed_workspace, active_item, seed_bin):
    """Verifies stock balances are maintained independently for each bin."""
    service = InventoryService(db_session)

    second_bin = Bin(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        code=f"SECOND-{uuid.uuid4().hex[:8].upper()}",
        zone="Second Test Warehouse",
        is_deleted=False,
    )

    db_session.add(second_bin)
    await db_session.commit()
    await db_session.refresh(second_bin)

    # Add stock to the first bin.
    await service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_change=20,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    # Add stock to the second bin.
    await service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=second_bin.id,
            quantity_change=10,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    first_inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    second_inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=second_bin.id,
    )

    assert first_inventory.quantity_on_hand == 20
    assert second_inventory.quantity_on_hand == 10


# ==============================================================================
# 4. STOCK MOVEMENTS
# ==============================================================================


@pytest.mark.asyncio
async def test_create_stock_movement_success(db_session, seed_workspace, active_item, seed_bin):
    """Verifies creating a stock movement updates on-hand quantity."""
    service = InventoryService(db_session)

    movement_data = StockMovementCreate(
        item_id=active_item.id,
        bin_id=seed_bin.id,
        quantity_change=50,
        reference_type=StockMovementType.MANUAL_ADJUSTMENT,
    )

    movement = await service.create_stock_movement(
        seed_workspace,
        movement_data,
    )

    assert movement.quantity_change == 50
    assert movement.item_id == active_item.id
    assert movement.bin_id == seed_bin.id

    inv = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    assert inv.quantity_on_hand == 50


@pytest.mark.asyncio
async def test_create_stock_movement_insufficient_stock(db_session, seed_workspace, active_item, seed_bin):
    """Verifies negative movements cannot reduce stock below zero."""
    service = InventoryService(db_session)

    movement_data = StockMovementCreate(
        item_id=active_item.id,
        bin_id=seed_bin.id,
        quantity_change=-10,
        reference_type=StockMovementType.MANUAL_ADJUSTMENT,
    )

    with pytest.raises(InsufficientInventoryError):
        await service.create_stock_movement(
            seed_workspace,
            movement_data,
        )


@pytest.mark.asyncio
async def test_get_stock_movements_pagination_and_filtering(db_session, seed_workspace, active_item, seed_bin):
    """Verifies retrieving and filtering stock movements."""
    service = InventoryService(db_session)

    await service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_change=10,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    await db_session.commit()

    # Fetch all movements.
    response = await service.get_stock_movements(seed_workspace)

    assert response.total >= 1

    # Filter by item.
    response_filtered = await service.get_stock_movements(
        seed_workspace,
        item_id=active_item.id,
    )

    assert response_filtered.total >= 1
    assert response_filtered.items[0].quantity_change == 10

    # Filter by bin.
    response_by_bin = await service.get_stock_movements(
        seed_workspace,
        bin_id=seed_bin.id,
    )

    assert response_by_bin.total >= 1
    assert response_by_bin.items[0].bin_id == seed_bin.id

    # Filter by nonexistent item.
    response_empty = await service.get_stock_movements(
        seed_workspace,
        item_id=uuid.uuid4(),
    )

    assert response_empty.total == 0


@pytest.mark.asyncio
async def test_create_stock_movement_does_not_affect_other_bins(db_session, seed_workspace, active_item, seed_bin):
    """Verifies a movement in one bin does not change another bin's stock."""
    service = InventoryService(db_session)

    second_bin = Bin(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        code=f"OTHER-{uuid.uuid4().hex[:8].upper()}",
        zone="Other Warehouse",
        is_deleted=False,
    )

    db_session.add(second_bin)
    await db_session.commit()

    await service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_change=25,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    first_inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    second_inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=second_bin.id,
    )

    assert first_inventory.quantity_on_hand == 25
    assert second_inventory.quantity_on_hand == 0


# ==============================================================================
# 5. INVENTORY RETRIEVAL AND VALIDATION
# ==============================================================================


@pytest.mark.asyncio
async def test_get_inventory_not_found(db_session, seed_workspace):
    """Retrieving a nonexistent inventory ID raises InventoryNotFoundError."""
    service = InventoryService(db_session)

    with pytest.raises(InventoryNotFoundError):
        await service.get_inventory(seed_workspace, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_inventory_returns_correct_bin_balance(db_session, seed_workspace, active_item, seed_bin):
    """Retrieves an inventory record by its ID."""
    service = InventoryService(db_session)

    inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    response = await service.get_inventory(
        seed_workspace,
        inventory.id,
    )

    assert response.id == inventory.id
    assert response.item_id == active_item.id
    assert response.bin_id == seed_bin.id
    assert response.quantity_on_hand == 0


# ==============================================================================
# 6. NEGATIVE STOCK MOVEMENTS
# ==============================================================================


@pytest.mark.asyncio
async def test_negative_stock_movement_success(db_session, seed_workspace, active_item, seed_bin):
    """A valid negative movement reduces stock in the selected bin."""
    service = InventoryService(db_session)

    await service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_change=30,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    movement = await service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=seed_bin.id,
            quantity_change=-10,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
            notes="Stock correction",
        ),
    )

    inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    assert movement.quantity_change == -10
    assert movement.notes == "Stock correction"
    assert inventory.quantity_on_hand == 20


@pytest.mark.asyncio
async def test_insufficient_stock_does_not_create_movement(db_session, seed_workspace, active_item, seed_bin):
    """A rejected movement must not change stock or create movement history."""
    service = InventoryService(db_session)

    with pytest.raises(InsufficientInventoryError):
        await service.create_stock_movement(
            seed_workspace,
            StockMovementCreate(
                item_id=active_item.id,
                bin_id=seed_bin.id,
                quantity_change=-10,
                reference_type=StockMovementType.MANUAL_ADJUSTMENT,
            ),
        )

    inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    movements = await service.get_stock_movements(
        seed_workspace,
        item_id=active_item.id,
        bin_id=seed_bin.id,
    )

    assert inventory.quantity_on_hand == 0
    assert movements.total == 0


# ==============================================================================
# 7. STOCK MOVEMENT PAGINATION
# ==============================================================================


@pytest.mark.asyncio
async def test_get_stock_movements_pagination(db_session, seed_workspace, active_item, seed_bin):
    """Verifies stock movement pagination and total count."""
    service = InventoryService(db_session)

    for quantity in [10, 20, 30]:
        await service.create_stock_movement(
            seed_workspace,
            StockMovementCreate(
                item_id=active_item.id,
                bin_id=seed_bin.id,
                quantity_change=quantity,
                reference_type=StockMovementType.MANUAL_ADJUSTMENT,
            ),
        )

    await db_session.commit()

    first_page = await service.get_stock_movements(
        seed_workspace,
        item_id=active_item.id,
        bin_id=seed_bin.id,
        page=1,
        limit=2,
    )

    second_page = await service.get_stock_movements(
        seed_workspace,
        item_id=active_item.id,
        bin_id=seed_bin.id,
        page=2,
        limit=2,
    )

    assert first_page.total == 3
    assert len(first_page.items) == 2

    assert second_page.total == 3
    assert len(second_page.items) == 1

    first_page_ids = {movement.id for movement in first_page.items}
    second_page_ids = {movement.id for movement in second_page.items}

    assert first_page_ids.isdisjoint(second_page_ids)


# ==============================================================================
# 8. BIN-SPECIFIC STOCK VALIDATION
# ==============================================================================


@pytest.mark.asyncio
async def test_insufficient_stock_in_one_bin_does_not_use_other_bin_stock(
    db_session, seed_workspace, active_item, seed_bin
):
    """Stock in another bin cannot satisfy a negative movement."""
    service = InventoryService(db_session)

    second_bin = Bin(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        code=f"SECOND-{uuid.uuid4().hex[:8].upper()}",
        zone="Second Warehouse",
        is_deleted=False,
    )

    db_session.add(second_bin)
    await db_session.commit()

    # The second bin has 50 units.
    await service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            bin_id=second_bin.id,
            quantity_change=50,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        ),
    )

    # The first bin has zero units. It cannot use the second bin's stock.
    with pytest.raises(InsufficientInventoryError):
        await service.create_stock_movement(
            seed_workspace,
            StockMovementCreate(
                item_id=active_item.id,
                bin_id=seed_bin.id,
                quantity_change=-10,
                reference_type=StockMovementType.MANUAL_ADJUSTMENT,
            ),
        )

    first_inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=seed_bin.id,
    )

    second_inventory = await service.get_inventory_by_item(
        seed_workspace,
        active_item.id,
        bin_id=second_bin.id,
    )

    assert first_inventory.quantity_on_hand == 0
    assert second_inventory.quantity_on_hand == 50
