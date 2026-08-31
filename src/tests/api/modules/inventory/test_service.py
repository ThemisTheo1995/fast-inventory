import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from src.erp.api.modules.inventory.enums import OrderType
from src.erp.api.modules.inventory.exceptions import InsufficientInventoryError
from src.erp.api.modules.inventory.models import Inventory
from src.erp.api.modules.inventory.schemas.stock_movement import StockMovementCreate
from src.erp.api.modules.inventory.service import InventoryService

# ==============================================================================
# 1. CORE HELPER TESTS (_get_or_create_inventory)
# ==============================================================================


def test_get_or_create_inventory_existing(db_session, seed_workspace, active_item):
    """Verifies it fetches the existing inventory."""
    service = InventoryService(db_session)
    inv = service._get_or_create_inventory(seed_workspace, active_item.id)
    assert inv.item_id == active_item.id


def test_get_or_create_inventory_creates_new(db_session, seed_workspace, empty_item):
    """Verifies it creates an inventory record initialized to 0 if missing."""
    service = InventoryService(db_session)
    inv = service._get_or_create_inventory(seed_workspace, empty_item.id)

    assert inv.item_id == empty_item.id
    assert inv.quantity_on_hand == 0
    assert inv.quantity_allocated == 0
    assert inv.quantity_on_order == 0


def test_get_or_create_inventory_race_condition(db_session, seed_workspace, empty_item):
    """
    Verifies that if two requests try to create the inventory simultaneously,
    the IntegrityError is caught and the newly inserted row is fetched.
    """
    service = InventoryService(db_session)

    original_execute = service.db.execute
    call_count = 0

    def fake_execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First check: pretend it doesn't exist
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            return mock_result
        if call_count == 2:
            # Retry check after IntegrityError: pretend the other request created it
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = Inventory(item_id=empty_item.id, workspace_id=seed_workspace)
            return mock_result
        return original_execute(stmt, *args, **kwargs)

    with (
        patch.object(service.db, "execute", side_effect=fake_execute),
        patch.object(service.db, "flush", side_effect=IntegrityError(None, None, BaseException())),
    ):
        inv = service._get_or_create_inventory(seed_workspace, empty_item.id, lock_for_update=True)
        assert inv.item_id == empty_item.id


# ==============================================================================
# 2. READ OPERATIONS
# ==============================================================================


def test_get_inventories_pagination_and_expand(db_session, seed_workspace, active_item):
    """Verifies fetching paginated lists and applying expand paths."""
    service = InventoryService(db_session)

    response = service.get_inventories(seed_workspace, page=1, limit=10, expand=["item"])

    assert response.total >= 1
    assert len(response.items) >= 1
    # Verify the item relationship was loaded due to `expand`
    assert response.items[0].item.sku == active_item.sku


def test_get_inventory_by_item(db_session, seed_workspace, active_item):
    """Verifies fetching inventory for a specific item ID."""
    service = InventoryService(db_session)
    inv = service.get_inventory_by_item(seed_workspace, active_item.id)
    assert inv.item_id == active_item.id


# ==============================================================================
# 3. STOCK MOVEMENTS
# ==============================================================================


def test_create_stock_movement_success(db_session, seed_workspace, active_item):
    """Verifies creating a stock movement updates the on-hand quantity."""
    service = InventoryService(db_session)

    movement_data = StockMovementCreate(
        item_id=active_item.id,
        quantity_change=50,
        reference_type=OrderType.MANUAL_ADJUSTMENT,
    )

    movement = service.create_stock_movement(seed_workspace, movement_data)

    assert movement.quantity_change == 50
    inv = service.get_inventory_by_item(seed_workspace, active_item.id)
    assert inv.quantity_on_hand == 50


def test_create_stock_movement_insufficient_stock(db_session, seed_workspace, active_item):
    """Verifies negative movements that drop stock below 0 are blocked."""
    service = InventoryService(db_session)

    movement_data = StockMovementCreate(
        item_id=active_item.id,
        quantity_change=-10,  # Starts at 0
        reference_type=OrderType.MANUAL_ADJUSTMENT,
    )

    with pytest.raises(InsufficientInventoryError):
        service.create_stock_movement(seed_workspace, movement_data)


def test_get_stock_movements_pagination_and_filtering(db_session, seed_workspace, active_item):
    """Verifies retrieving and filtering stock movements."""
    service = InventoryService(db_session)

    # Add a movement
    service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(item_id=active_item.id, quantity_change=10, reference_type=OrderType.MANUAL_ADJUSTMENT),
    )
    db_session.commit()

    # Test unfettered fetch
    response = service.get_stock_movements(seed_workspace)
    assert response.total >= 1

    # Test filtered by item_id
    response_filtered = service.get_stock_movements(seed_workspace, item_id=active_item.id)
    assert response_filtered.total >= 1
    assert response_filtered.items[0].quantity_change == 10

    # Test empty filter
    fake_id = uuid.uuid4()
    response_empty = service.get_stock_movements(seed_workspace, item_id=fake_id)
    assert response_empty.total == 0


# ==============================================================================
# 4. QUANTITY ALLOCATIONS & ON-ORDER ADJUSTMENTS
# ==============================================================================


def test_adjust_quantity_on_order(db_session, seed_workspace, active_item):
    """Verifies adjustments to quantity_on_order."""
    service = InventoryService(db_session)

    # Zero delta does nothing
    service.adjust_quantity_on_order(seed_workspace, active_item.id, 0)
    inv = service.get_inventory_by_item(seed_workspace, active_item.id)
    assert inv.quantity_on_order == 0

    # Positive delta
    service.adjust_quantity_on_order(seed_workspace, active_item.id, 10)
    inv = service.get_inventory_by_item(seed_workspace, active_item.id)
    assert inv.quantity_on_order == 10

    # Negative delta
    service.adjust_quantity_on_order(seed_workspace, active_item.id, -5)
    inv = service.get_inventory_by_item(seed_workspace, active_item.id)
    assert inv.quantity_on_order == 5

    # Negative delta going below 0 fails
    with pytest.raises(InsufficientInventoryError):
        service.adjust_quantity_on_order(seed_workspace, active_item.id, -10)


def test_adjust_quantity_allocated(db_session, seed_workspace, active_item):
    """Verifies adjustments to quantity_allocated and over-allocation constraints."""
    service = InventoryService(db_session)

    # Seed on-hand inventory so we can allocate it
    service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(item_id=active_item.id, quantity_change=20, reference_type=OrderType.MANUAL_ADJUSTMENT),
    )
    db_session.commit()

    # Zero delta does nothing
    service.adjust_quantity_allocated(seed_workspace, active_item.id, 0)

    # Positive delta (Success)
    service.adjust_quantity_allocated(seed_workspace, active_item.id, 15)
    inv = service.get_inventory_by_item(seed_workspace, active_item.id)
    assert inv.quantity_allocated == 15

    # Positive delta (Failure: exceeding on-hand - allocated = 5)
    with pytest.raises(InsufficientInventoryError):
        service.adjust_quantity_allocated(seed_workspace, active_item.id, 10)

    # Negative delta (Success)
    service.adjust_quantity_allocated(seed_workspace, active_item.id, -5)
    inv = service.get_inventory_by_item(seed_workspace, active_item.id)
    assert inv.quantity_allocated == 10

    # Negative delta (Failure: going below 0)
    with pytest.raises(InsufficientInventoryError):
        service.adjust_quantity_allocated(seed_workspace, active_item.id, -15)
