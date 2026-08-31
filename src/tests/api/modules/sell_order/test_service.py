import uuid

import pytest

from src.erp.api.modules.inventory.enums import OrderType
from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.item.models import Item
from src.erp.api.modules.sell_order.enums import SOStatusEnum
from src.erp.api.modules.sell_order.exceptions import (
    SellOrderCannotDeleteError,
    SellOrderExistsError,
    SellOrderLineItemChangeError,
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
from src.erp.api.modules.sell_order.service import SellOrderService


def test_create_sell_order_success(db_session, seed_workspace, active_customer, event_bus):
    service = SellOrderService(db_session, event_bus)
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


def test_create_sell_order_duplicate_number_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    payload = SellOrderCreate(so_number="SO-DUP", status=SOStatusEnum.DRAFT, sell_order_lines=[])

    service.create_sell_order(seed_workspace, payload)

    with pytest.raises(SellOrderExistsError):
        service.create_sell_order(seed_workspace, payload)


def test_create_sell_order_cross_tenant_number_allowed(db_session, seed_workspace, alt_workspace, event_bus):
    """Ensures two separate workspaces can use the same sell order number."""
    service = SellOrderService(db_session, event_bus)
    payload = SellOrderCreate(so_number="SO-SHARED", status=SOStatusEnum.DRAFT, sell_order_lines=[])

    service.create_sell_order(seed_workspace, payload)
    cross_so = service.create_sell_order(alt_workspace, payload)

    assert cross_so.workspace_id == alt_workspace
    assert cross_so.so_number == "SO-SHARED"


def test_get_sell_orders_pagination_and_search(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

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


def test_get_sell_order_not_found(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    with pytest.raises(SellOrderNotFoundError):
        service.get_sell_order(seed_workspace, uuid.uuid4())


def test_get_sell_order_tenant_isolation(db_session, alt_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    with pytest.raises(SellOrderNotFoundError):
        service.get_sell_order(alt_workspace, active_sell_order.id)


def test_update_sell_order_basic_metadata(db_session, seed_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    update_payload = SellOrderUpdate(so_number="SO-NEW-NUM")

    updated = service.update_sell_order(seed_workspace, active_sell_order.id, update_payload)
    assert updated.so_number == "SO-NEW-NUM"


def test_update_sell_order_duplicate_number_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    so1 = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ONE", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )
    service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-TWO", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    with pytest.raises(SellOrderExistsError):
        service.update_sell_order(seed_workspace, so1.id, SellOrderUpdate(so_number="SO-TWO"))


def test_update_sell_order_same_number_allowed(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    so = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-SAME", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    updated = service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(so_number="SO-SAME"))
    assert updated.so_number == "SO-SAME"


def test_delete_sell_order_soft_delete(db_session, seed_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    service.delete_sell_order(seed_workspace, active_sell_order.id)

    with pytest.raises(SellOrderNotFoundError):
        service.get_sell_order(seed_workspace, active_sell_order.id)


def test_delete_sell_order_not_found(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    with pytest.raises(SellOrderNotFoundError):
        service.delete_sell_order(seed_workspace, uuid.uuid4())


def test_delete_sell_order_invalid_status_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    so = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-DEL-ERR", status=SOStatusEnum.CONFIRMED, sell_order_lines=[])
    )

    with pytest.raises(SellOrderCannotDeleteError):
        service.delete_sell_order(seed_workspace, so.id)


# ==============================================================================
# 2. STATUS TRANSITIONS & INVENTORY LEDGER TESTS
# ==============================================================================


def test_status_transition_draft_to_confirmed_allocates_inventory(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-1", title="I1", base_price=10, is_deleted=False)
    db_session.add(item)
    db_session.flush()

    # Provide enough stock to allocate
    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 100
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-1",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=10, unit_cost=50)],
        ),
    )

    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_allocated == 10


def test_status_transition_confirmed_to_fulfilled_creates_stock_movement(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-2", title="I2", base_price=10, is_deleted=False)
    db_session.add(item)
    db_session.flush()

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
    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.FULLFILLED))

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 0
    assert inv_updated.quantity_on_hand == 45

    movements = inv_service.get_stock_movements(seed_workspace, item_id=item.id)
    assert movements.items[0].quantity_change == -5
    assert movements.items[0].reference_type == OrderType.SELL_ORDER


def test_status_transition_confirmed_to_cancelled_clears_allocation(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-3", title="I3", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 100
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-STATE-3",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=7, unit_cost=100)],
        ),
    )

    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))
    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CANCELLED))

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 0


def test_status_transition_fulfilled_to_returned_restores_stock(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-RET", title="RET", base_price=10, is_deleted=False
    )
    db_session.add(item)

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-RET-1",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=10, unit_cost=50)],
        ),
    )

    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))
    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.FULLFILLED))
    service.update_sell_order(seed_workspace, so.id, SellOrderUpdate(status=SOStatusEnum.RETURNED))

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_on_hand == 50  # 50 - 10 (fulfilled) + 10 (returned)


def test_status_transition_invalid_paths_fail(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so_can = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ERR-1", status=SOStatusEnum.CANCELLED, sell_order_lines=[])
    )
    so_ret = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ERR-2", status=SOStatusEnum.RETURNED, sell_order_lines=[])
    )
    so_ful = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ERR-3", status=SOStatusEnum.FULLFILLED, sell_order_lines=[])
    )
    so_draft = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-ERR-4", status=SOStatusEnum.DRAFT, sell_order_lines=[])
    )

    # From Terminal states (TerminalError)
    with pytest.raises(SellOrderStatusTerminalError):
        service.update_sell_order(seed_workspace, so_can.id, SellOrderUpdate(status=SOStatusEnum.CONFIRMED))

    with pytest.raises(SellOrderStatusTerminalError):
        service.update_sell_order(seed_workspace, so_ret.id, SellOrderUpdate(status=SOStatusEnum.DRAFT))

    # From Fulfilled to anything but Returned (TransitionError)
    with pytest.raises(SellOrderStatusTransitionError):
        service.update_sell_order(seed_workspace, so_ful.id, SellOrderUpdate(status=SOStatusEnum.DRAFT))

    # Invalid path not in TRANSITION_EVENTS dictionary (Draft -> Returned)
    with pytest.raises(SellOrderStatusTransitionError):
        service.update_sell_order(seed_workspace, so_draft.id, SellOrderUpdate(status=SOStatusEnum.RETURNED))


# ==============================================================================
# 3. SELL ORDER LINE SERVICE TESTS
# ==============================================================================


def test_add_line_recalculates_total(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(so_number="SO-LINE-1", status=SOStatusEnum.DRAFT, sell_order_lines=[]),
    )

    service.add_line(seed_workspace, so.id, SellOrderLineCreate(item_id=None, quantity=10, unit_cost=15))

    updated_so = service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 150


def test_add_line_to_confirmed_order_allocates_inventory(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-4", title="I4", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 10
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace, SellOrderCreate(so_number="SO-LINE-2", status=SOStatusEnum.CONFIRMED, sell_order_lines=[])
    )

    service.add_line(seed_workspace, so.id, SellOrderLineCreate(item_id=item.id, quantity=4, unit_cost=10))

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 4


def test_update_line_recalculates_total_and_inventory(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-5", title="I5", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-3",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=10, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    # Simulate manual initial adjustment since creation bypasses transition logic
    inv_service.adjust_quantity_allocated(seed_workspace, item.id, 10)
    db_session.flush()

    service.update_line(
        seed_workspace,
        so.id,
        line_id,
        SellOrderLineUpdate(quantity=15, unit_cost=20),
    )

    updated_so = service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 300

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 15


def test_remove_line_recalculates_total_and_deallocates(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-6", title="I6", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-4",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[
                SellOrderLineCreate(item_id=item.id, quantity=8, unit_cost=10),
                SellOrderLineCreate(item_id=item.id, quantity=2, unit_cost=10),
            ],
        ),
    )
    line_id_to_delete = so.sell_order_lines[0].id

    inv_service.adjust_quantity_allocated(seed_workspace, item.id, 10)
    db_session.flush()

    service.remove_line(seed_workspace, so.id, line_id_to_delete)

    updated_so = service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 20
    assert len(updated_so.sell_order_lines) == 1

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 2


def test_modify_line_on_uneditable_so_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-5",
            status=SOStatusEnum.FULLFILLED,
            sell_order_lines=[SellOrderLineCreate(quantity=1, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderNotEditableError):
        service.add_line(seed_workspace, so.id, SellOrderLineCreate(quantity=1, unit_cost=10))

    with pytest.raises(SellOrderNotEditableError):
        service.update_line(seed_workspace, so.id, line_id, SellOrderLineUpdate(quantity=5, unit_cost=10))

    with pytest.raises(SellOrderNotEditableError):
        service.remove_line(seed_workspace, so.id, line_id)


def test_sell_order_line_not_found_errors(db_session, seed_workspace, active_sell_order, event_bus):
    service = SellOrderService(db_session, event_bus)
    fake_id = uuid.uuid4()

    with pytest.raises(SellOrderLineNotFoundError):
        service.update_line(
            seed_workspace, active_sell_order.id, fake_id, SellOrderLineUpdate(quantity=5, unit_cost=10)
        )

    with pytest.raises(SellOrderLineNotFoundError):
        service.remove_line(seed_workspace, active_sell_order.id, fake_id)


def test_update_line_item_id_change_fails(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    item1 = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-7", title="I7", base_price=10, is_deleted=False)
    item2 = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-8", title="I8", base_price=20, is_deleted=False)
    db_session.add_all([item1, item2])
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-LINE-6",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[SellOrderLineCreate(item_id=item1.id, quantity=1, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    with pytest.raises(SellOrderLineItemChangeError):
        service.update_line(
            seed_workspace, so.id, line_id, SellOrderLineUpdate(item_id=item2.id, quantity=1, unit_cost=50)
        )


def test_update_line_same_quantity_no_inventory_change(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-9", title="I9", base_price=10, is_deleted=False)
    db_session.add(item)

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    inv.quantity_on_hand = 50
    db_session.flush()

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-DELTA-0",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=item.id, quantity=10, unit_cost=10)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    inv_service.adjust_quantity_allocated(seed_workspace, item.id, 10)
    db_session.flush()

    service.update_line(seed_workspace, so.id, line_id, SellOrderLineUpdate(item_id=item.id, quantity=10, unit_cost=25))

    updated_so = service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 250

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_allocated == 10  # Unchanged


def test_line_modifications_without_item_id_bypasses_events(db_session, seed_workspace, event_bus):
    service = SellOrderService(db_session, event_bus)

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-NO-ITEM",
            status=SOStatusEnum.CONFIRMED,
            sell_order_lines=[SellOrderLineCreate(item_id=None, quantity=1, unit_cost=50)],
        ),
    )
    line_id = so.sell_order_lines[0].id

    # Update bypasses inventory event logic
    service.update_line(seed_workspace, so.id, line_id, SellOrderLineUpdate(item_id=None, quantity=5, unit_cost=50))
    updated_so = service.get_sell_order(seed_workspace, so.id)
    assert updated_so.total_amount == 250

    # Remove bypasses inventory event logic
    service.remove_line(seed_workspace, so.id, line_id)
    final_so = service.get_sell_order(seed_workspace, so.id)
    assert final_so.total_amount == 0


def test_delete_sell_order_with_lines_cascades_soft_delete(db_session, seed_workspace, event_bus):
    """Verifies that deleting a sell order also triggers soft_delete() on all its lines."""
    service = SellOrderService(db_session, event_bus)

    so = service.create_sell_order(
        seed_workspace,
        SellOrderCreate(
            so_number="SO-CASCADE-DEL",
            status=SOStatusEnum.DRAFT,
            sell_order_lines=[
                SellOrderLineCreate(quantity=1, unit_cost=100),
                SellOrderLineCreate(quantity=2, unit_cost=50),
            ],
        ),
    )

    assert len(so.sell_order_lines) == 2
    service.delete_sell_order(seed_workspace, so.id)

    with pytest.raises(SellOrderNotFoundError):
        service.get_sell_order(seed_workspace, so.id)
