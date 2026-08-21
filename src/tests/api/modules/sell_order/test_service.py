import uuid

import pytest

from src.erp.api.modules.inventory.enums import OrderType
from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.item.models import Item
from src.erp.api.modules.sell_order.enums import SOStatusEnum
from src.erp.api.modules.sell_order.exceptions import (
    SellOrderExistsError,
    SellOrderLineNotFoundError,
    SellOrderNotEditableError,
    SellOrderNotFoundError,
    SellOrderStatusTerminalError,
    SellOrderStatusTransitionError,
)
from src.erp.api.modules.sell_order.schemas import (
    SellOrderCreate,
    SellOrderLineCreate,
    SellOrderLineUpdate,
    SellOrderUpdate,
)
from src.erp.api.modules.sell_order.service import SellOrderLineService, SellOrderService

# ==============================================================================
# 1. SELL ORDER SERVICE & TENANT ISOLATION TESTS
# ==============================================================================


def test_create_sell_order_success(db_session, seed_workspace, active_customer):
    service = SellOrderService(db_session)
    payload = SellOrderCreate(
        so_number="SO-100",
        customer_id=active_customer.id,
        status=SOStatusEnum.DRAFT,
        sell_order_lines=[
            SellOrderLineCreate(quantity=2, unit_cost=500),
            SellOrderLineCreate(quantity=3, unit_cost=100),
        ],
    )

    so = service.create_sell_order(seed_workspace, payload)
    assert so.id is not None
    assert so.so_number == "SO-100"
    assert so.total_amount == 1300
    assert so.workspace_id == seed_workspace
    assert len(so.sell_order_lines) == 2


def test_create_sell_order_duplicate_number_fails(db_session, seed_workspace):
    service = SellOrderService(db_session)
    payload = SellOrderCreate(so_number="SO-DUP", status=SOStatusEnum.DRAFT, sell_order_lines=[])

    service.create_sell_order(seed_workspace, payload)

    with pytest.raises(SellOrderExistsError):
        service.create_sell_order(seed_workspace, payload)


def test_create_sell_order_cross_tenant_number_allowed(db_session, seed_workspace, alt_workspace):
    """Ensures two separate workspaces can use the same sell order number."""
    service = SellOrderService(db_session)
    payload = SellOrderCreate(so_number="SO-SHARED", status=SOStatusEnum.DRAFT, sell_order_lines=[])

    service.create_sell_order(seed_workspace, payload)
    cross_so = service.create_sell_order(alt_workspace, payload)

    assert cross_so.workspace_id == alt_workspace
    assert cross_so.so_number == "SO-SHARED"


def test_get_sell_orders_pagination_and_search(db_session, seed_workspace):
    service = SellOrderService(db_session)

    service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="APPLE-1", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )
    service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="APPLE-2", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )
    service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="BANANA-1", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    res = service.get_sell_orders(seed_workspace, page=1, limit=2)
    assert len(res.items) == 2
    assert res.total >= 3

    search_res = service.get_sell_orders(seed_workspace, search="APPLE")
    assert len(search_res.items) == 2


def test_update_sell_order_duplicate_number_fails(db_session, seed_workspace):
    service = SellOrderService(db_session)
    so1 = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ONE", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )
    service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-TWO", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    with pytest.raises(SellOrderExistsError):
        service.update_sell_order(seed_workspace, so1.id, SellOrderUpdate(so_number="SO-TWO"))


def test_get_sell_order_not_found(db_session, seed_workspace):
    service = SellOrderService(db_session)
    with pytest.raises(SellOrderNotFoundError):
        service.get_sell_order(seed_workspace, uuid.uuid4())


def test_delete_sell_order_not_found(db_session, seed_workspace):
    service = SellOrderService(db_session)
    with pytest.raises(SellOrderNotFoundError):
        service.delete_sell_order(seed_workspace, uuid.uuid4())


def test_get_sell_order_tenant_isolation(db_session, alt_workspace, active_sell_order):
    service = SellOrderService(db_session)
    with pytest.raises(SellOrderNotFoundError):
        service.get_sell_order(alt_workspace, active_sell_order.id)


def test_update_sell_order_basic_metadata(db_session, seed_workspace, active_sell_order):
    service = SellOrderService(db_session)
    update_payload = SellOrderUpdate(so_number="SO-NEW-NUM")

    updated = service.update_sell_order(seed_workspace, active_sell_order.id, update_payload)
    assert updated.so_number == "SO-NEW-NUM"


def test_delete_sell_order_soft_delete(db_session, seed_workspace, active_sell_order):
    service = SellOrderService(db_session)
    service.delete_sell_order(seed_workspace, active_sell_order.id)

    with pytest.raises(SellOrderNotFoundError):
        service.get_sell_order(seed_workspace, active_sell_order.id)


def test_status_transition_with_non_inventory_line(db_session, seed_workspace):
    """Skipping inventory allocation for lines without an item_id."""
    service = SellOrderService(db_session)
    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-GAP-65",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=None, quantity=2, unit_cost=50)],
        ),
    )
    updated = service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))
    assert updated.status == SOStatusEnum.CONFIRMED


def test_status_transition_fallback_case(db_session, seed_workspace):
    service = SellOrderService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Fallback Test Item",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-GAP-98",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=1, unit_cost=100)],
        ),
    )

    updated = service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CANCELLED))
    assert updated.status == SOStatusEnum.CANCELLED


def test_delete_sell_order_with_lines_cascades_soft_delete(db_session, seed_workspace):
    service = SellOrderService(db_session)
    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-GAP-179",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(quantity=1, unit_cost=100)],
        ),
    )
    service.delete_sell_order(seed_workspace, so.id)

    with pytest.raises(SellOrderNotFoundError):
        service.get_sell_order(seed_workspace, so.id)


# ==============================================================================
# 2. STATUS TRANSITIONS & INVENTORY LEDGER TESTS
# ==============================================================================


def test_status_transition_draft_to_confirmed_allocates_inventory(db_session, seed_workspace, stocked_item):
    service = SellOrderService(db_session)
    inv_service = InventoryService(db_session)

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-1",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=stocked_item.id, quantity=10, unit_cost=50)],
        ),
    )

    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))

    inv = inv_service.get_inventory_by_item(seed_workspace, stocked_item.id)
    assert inv.quantity_allocated == 10


def test_status_transition_confirmed_to_fullfilled_creates_stock_movement(db_session, seed_workspace):
    service = SellOrderService(db_session)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item 2",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    # Pre-seed physical stock on hand using inventory service
    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-2",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=5, unit_cost=50)],
        ),
    )

    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))
    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status="FULLFILLED"))

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 0
    assert inv_updated.quantity_on_hand == 45

    movements = inv_service.get_stock_movements(seed_workspace, item_id=item.id)
    assert movements.total == 1
    assert movements.items[0].quantity_change == -5
    assert movements.items[0].reference_type == OrderType.SELL_ORDER


def test_status_transition_confirmed_to_cancelled_clears_allocation(db_session, seed_workspace, stocked_item):
    service = SellOrderService(db_session)
    inv_service = InventoryService(db_session)

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-3",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=stocked_item.id, quantity=7, unit_cost=100)],
        ),
    )

    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))
    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CANCELLED))

    inv = inv_service.get_inventory_by_item(seed_workspace, stocked_item.id)
    assert inv.quantity_allocated == 0


def test_status_transition_from_terminal_states_fails(db_session, seed_workspace):
    service = SellOrderService(db_session)

    so_rec = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-T1", status="FULLFILLED", sell_order_lines=[])
    )
    so_can = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-T2", status=SOStatusEnum.CANCELLED, sell_order_lines=[])
    )

    with pytest.raises(SellOrderStatusTransitionError):
        service.update_sell_order(seed_workspace, so_rec.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))

    with pytest.raises(SellOrderStatusTerminalError):
        service.update_sell_order(seed_workspace, so_can.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))


# ==============================================================================
# 3. SELL ORDER LINE SERVICE TESTS
# ==============================================================================


def test_add_line_recalculates_total(db_session, seed_workspace):
    so_service = SellOrderService(db_session)
    line_service = SellOrderLineService(db_session)

    so = so_service.create_sell_order(
        seed_workspace,
        SellOrderCreate(so_number="SO-LINE-1", status=SOStatusEnum.DRAFT, sell_order_lines=[]),
    )

    line_service.add_line(seed_workspace, so.id, SellOrderLineCreate(item_id=None, quantity=10, unit_cost=15))

    updated_so = so_service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 150


def test_add_line_to_confirmed_order_allocates_inventory(db_session, seed_workspace, stocked_item):
    so_service = SellOrderService(db_session)
    line_service = SellOrderLineService(db_session)
    inv_service = InventoryService(db_session)

    so = so_service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-LINE-2", status=SOStatusEnum.CONFIRMED, sell_order_lines=[])
    )

    line_service.add_line(seed_workspace, so.id, SellOrderLineCreate(item_id=stocked_item.id, quantity=4, unit_cost=10))

    inv = inv_service.get_inventory_by_item(seed_workspace, stocked_item.id)
    assert inv.quantity_allocated == 4


def test_update_line_recalculates_total_and_inventory(db_session, seed_workspace, stocked_item):
    so_service = SellOrderService(db_session)
    line_service = SellOrderLineService(db_session)
    inv_service = InventoryService(db_session)

    so = so_service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-3",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=stocked_item.id, quantity=10, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    inv_service.adjust_quantity_allocated(seed_workspace, stocked_item.id, 10)
    db_session.flush()

    line_service.update_line(
        seed_workspace,
        so.id,
        line_id,
        SellOrderLineUpdate(quantity=15, unit_cost=20),
    )

    updated_so = so_service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 300

    inv = inv_service.get_inventory_by_item(seed_workspace, stocked_item.id)
    assert inv.quantity_allocated == 15


def test_remove_line_recalculates_total(db_session, seed_workspace):
    so_service = SellOrderService(db_session)
    line_service = SellOrderLineService(db_session)

    so = so_service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-4",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[
                SellOrderLineCreate(quantity=2, unit_cost=100),
                SellOrderLineCreate(quantity=3, unit_cost=100),
            ],
        ),
    )
    assert so.total_amount == 500
    line_id_to_delete = so.sell_order_lines[0].id

    line_service.remove_line(seed_workspace, so.id, line_id_to_delete)

    updated_so = so_service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 300
    assert len(updated_so.sell_order_lines) == 1


def test_remove_line_from_confirmed_order_deallocates_inventory(db_session, seed_workspace, stocked_item):
    so_service = SellOrderService(db_session)
    line_service = SellOrderLineService(db_session)
    inv_service = InventoryService(db_session)

    so = so_service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-5",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=stocked_item.id, quantity=8, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id
    inv_service.adjust_quantity_allocated(seed_workspace, stocked_item.id, 8)
    db_session.flush()

    line_service.remove_line(seed_workspace, so.id, line_id)

    inv = inv_service.get_inventory_by_item(seed_workspace, stocked_item.id)
    assert inv.quantity_allocated == 0


def test_modify_line_on_terminal_so_fails(db_session, seed_workspace):
    so_service = SellOrderService(db_session)
    line_service = SellOrderLineService(db_session)

    so = so_service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-6",
            status="FULLFILLED",
            sell_order_lines=[SellOrderLineCreate(quantity=1, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderNotEditableError):
        line_service.add_line(seed_workspace, so.id, SellOrderLineCreate(quantity=1, unit_cost=10))

    with pytest.raises(SellOrderNotEditableError):
        line_service.update_line(seed_workspace, so.id, line_id, SellOrderLineUpdate(quantity=5, unit_cost=10))

    with pytest.raises(SellOrderNotEditableError):
        line_service.remove_line(seed_workspace, so.id, line_id)


def test_sell_order_line_not_found_errors(db_session, seed_workspace, active_sell_order):
    line_service = SellOrderLineService(db_session)

    # Parent sell order not found when adding line
    with pytest.raises(SellOrderNotFoundError):
        line_service.add_line(seed_workspace, uuid.uuid4(), SellOrderLineCreate(quantity=1, unit_cost=10))

    # Line not found when updating (must include unit_cost due to schema requirements)
    with pytest.raises(SellOrderLineNotFoundError):
        line_service.update_line(
            seed_workspace, active_sell_order.id, uuid.uuid4(), SellOrderLineUpdate(quantity=5, unit_cost=10)
        )

    # Line not found when removing
    with pytest.raises(SellOrderLineNotFoundError):
        line_service.remove_line(seed_workspace, active_sell_order.id, uuid.uuid4())


def test_update_line_on_draft_order_recalculates_total_only(db_session, seed_workspace):
    so_service = SellOrderService(db_session)
    line_service = SellOrderLineService(db_session)

    so = so_service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-DRAFT-LINE",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(quantity=2, unit_cost=100)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    updated_line = line_service.update_line(
        seed_workspace,
        so.id,
        line_id,
        SellOrderLineUpdate(quantity=5, unit_cost=100),
    )
    assert updated_line.quantity == 5

    updated_so = so_service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 500


def test_sell_order_line_cross_tenant_isolation_fails(db_session, alt_workspace, active_sell_order):
    line_service = SellOrderLineService(db_session)

    with pytest.raises(SellOrderNotFoundError):
        line_service.add_line(alt_workspace, active_sell_order.id, SellOrderLineCreate(quantity=1, unit_cost=10))
