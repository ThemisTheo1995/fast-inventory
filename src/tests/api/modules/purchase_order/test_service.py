import uuid

import pytest
from pydantic import ValidationError

from src.erp.api.modules.inventory.enums import OrderType
from src.erp.api.modules.inventory.handlers import register_inventory_handlers
from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.item.models import Item
from src.erp.api.modules.purchase_order.enums import POStatusEnum
from src.erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderCannotDeleteError,
    PurchaseOrderExistsError,
    PurchaseOrderLineItemChangeError,
    PurchaseOrderLineNotFoundError,
    PurchaseOrderNotEditableError,
    PurchaseOrderNotFoundError,
    PurchaseOrderStatusTransitionError,
)
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine
from src.erp.api.modules.purchase_order.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineUpdate,
    PurchaseOrderUpdate,
)
from src.erp.api.modules.purchase_order.service import PurchaseOrderService
from src.erp.api.modules.supplier.models import Supplier
from src.erp.core.event_bus import EventBus

# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def event_bus() -> EventBus:
    """Provides a fresh EventBus instance with inventory listeners wired up."""
    bus = EventBus()
    register_inventory_handlers(bus)
    return bus


@pytest.fixture
def active_supplier(db_session, seed_workspace) -> Supplier:
    """Seeds a live supplier record attached to the primary workspace."""
    supplier = Supplier(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        name="Active Supplier",
        email="active.supplier@test.com",
        is_deleted=False,
    )
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


@pytest.fixture
def active_purchase_order(db_session, seed_workspace, active_supplier) -> PurchaseOrder:
    """Seeds a live purchase order record attached to the primary workspace and active supplier."""
    purchase_order = PurchaseOrder(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        supplier_id=active_supplier.id,
        po_number="PO-FIXTURE-001",
        total_amount=1250,
        status=POStatusEnum.DRAFT,
    )
    db_session.add(purchase_order)
    db_session.commit()
    db_session.refresh(purchase_order)
    return purchase_order


@pytest.fixture
def active_purchase_order_line(db_session, active_purchase_order) -> PurchaseOrderLine:
    """Seeds a single purchase order line attached to the active_purchase_order."""
    purchase_order_line = PurchaseOrderLine(
        id=uuid.uuid4(),
        purchase_order_id=active_purchase_order.id,
        item_id=None,
        quantity=5,
        unit_cost=250,
    )
    db_session.add(purchase_order_line)
    db_session.commit()
    db_session.refresh(purchase_order_line)
    return purchase_order_line


# ==============================================================================
# 1. PURCHASE ORDER SERVICE: CRUD & TENANT ISOLATION
# ==============================================================================


def test_create_purchase_order_success(db_session, seed_workspace, active_supplier, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    payload = PurchaseOrderCreate(
        po_number="PO-100",
        supplier_id=active_supplier.id,
        status=POStatusEnum.DRAFT,
        total_amount=1300,
        purchase_order_lines=[
            PurchaseOrderLineCreate(quantity=2, unit_cost=500),
            PurchaseOrderLineCreate(quantity=3, unit_cost=100),
        ],
    )

    po = service.create_purchase_order(seed_workspace, payload)
    assert po.id is not None
    assert po.po_number == "PO-100"
    assert po.total_amount == 1300
    assert po.workspace_id == seed_workspace
    assert len(po.purchase_order_lines) == 2


def test_create_purchase_order_duplicate_number_fails(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    payload = PurchaseOrderCreate(po_number="PO-DUP", status=POStatusEnum.DRAFT, purchase_order_lines=[])

    service.create_purchase_order(seed_workspace, payload)

    with pytest.raises(PurchaseOrderExistsError):
        service.create_purchase_order(seed_workspace, payload)


def test_create_purchase_order_cross_tenant_number_allowed(db_session, seed_workspace, alt_workspace, event_bus):
    """Ensures two separate workspaces can use the same purchase order number."""
    service = PurchaseOrderService(db_session, event_bus)
    payload = PurchaseOrderCreate(po_number="PO-SHARED", status=POStatusEnum.DRAFT, purchase_order_lines=[])

    service.create_purchase_order(seed_workspace, payload)
    cross_po = service.create_purchase_order(alt_workspace, payload)

    assert cross_po.workspace_id == alt_workspace
    assert cross_po.po_number == "PO-SHARED"


def test_get_purchase_orders_pagination_and_search(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)

    service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="APPLE-1", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )
    service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="APPLE-2", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )
    service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="BANANA-1", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )

    res = service.get_purchase_orders(seed_workspace, page=1, limit=2)
    assert len(res.items) == 2
    assert res.total >= 3

    search_res = service.get_purchase_orders(seed_workspace, search="APPLE")
    assert len(search_res.items) == 2


def test_get_purchase_order_not_found(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    with pytest.raises(PurchaseOrderNotFoundError):
        service.get_purchase_order(seed_workspace, uuid.uuid4())


def test_get_purchase_order_tenant_isolation(db_session, alt_workspace, active_purchase_order, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    with pytest.raises(PurchaseOrderNotFoundError):
        service.get_purchase_order(alt_workspace, active_purchase_order.id)


def test_update_purchase_order_basic_metadata(db_session, seed_workspace, active_purchase_order, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    update_payload = PurchaseOrderUpdate(po_number="PO-NEW-NUM")

    updated = service.update_purchase_order(seed_workspace, active_purchase_order.id, update_payload)
    assert updated.po_number == "PO-NEW-NUM"


def test_update_purchase_order_duplicate_number_fails(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    po1 = service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-ONE", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )
    service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-TWO", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )

    with pytest.raises(PurchaseOrderExistsError):
        service.update_purchase_order(seed_workspace, po1.id, PurchaseOrderUpdate(po_number="PO-TWO"))


def test_update_purchase_order_same_number_allowed(db_session, seed_workspace, event_bus):
    """Verifies that updating a PO without changing its po_number does not trigger a unique constraint error."""
    service = PurchaseOrderService(db_session, event_bus)
    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(po_number="PO-SAME-NUM", status=POStatusEnum.DRAFT, purchase_order_lines=[]),
    )

    updated_po = service.update_purchase_order(
        seed_workspace, po.id, PurchaseOrderUpdate(po_number="PO-SAME-NUM", status=POStatusEnum.SENT)
    )
    assert updated_po.status == POStatusEnum.SENT


def test_delete_purchase_order_soft_delete(db_session, seed_workspace, active_purchase_order, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    service.delete_purchase_order(seed_workspace, active_purchase_order.id)

    with pytest.raises(PurchaseOrderNotFoundError):
        service.get_purchase_order(seed_workspace, active_purchase_order.id)


def test_delete_purchase_order_not_found(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    with pytest.raises(PurchaseOrderNotFoundError):
        service.delete_purchase_order(seed_workspace, uuid.uuid4())


def test_delete_purchase_order_with_lines_cascades_soft_delete(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-179",
            status=POStatusEnum.DRAFT,
            total_amount=100,
            purchase_order_lines=[PurchaseOrderLineCreate(quantity=1, unit_cost=100)],
        ),
    )
    service.delete_purchase_order(seed_workspace, po.id)

    with pytest.raises(PurchaseOrderNotFoundError):
        service.get_purchase_order(seed_workspace, po.id)


def test_delete_purchase_order_fails_if_not_draft_or_cancelled(db_session, seed_workspace, event_bus):
    """Verifies that deleting a PO in a SENT or RECEIVED status raises PurchaseOrderCannotDeleteError."""
    service = PurchaseOrderService(db_session, event_bus)
    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(po_number="PO-DEL-ERR", status=POStatusEnum.SENT, purchase_order_lines=[]),
    )

    with pytest.raises(PurchaseOrderCannotDeleteError):
        service.delete_purchase_order(seed_workspace, po.id)


# ==============================================================================
# 2. PURCHASE ORDER STATUS TRANSITIONS & EVENT-DRIVEN INVENTORY TESTS
# ==============================================================================


def test_status_transition_draft_to_sent_adds_on_order(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-1",
            status=POStatusEnum.DRAFT,
            total_amount=500,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=10, unit_cost=50)],
        ),
    )

    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 10


def test_status_transition_sent_to_received_creates_stock_movement(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
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

    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-2",
            status=POStatusEnum.DRAFT,
            total_amount=250,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=5, unit_cost=50)],
        ),
    )

    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))
    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.RECEIVED))

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_on_order == 0

    movements = inv_service.get_stock_movements(seed_workspace, item_id=item.id)
    assert movements.total == 1
    assert movements.items[0].quantity_change == 5
    assert movements.items[0].reference_type == OrderType.PURCHASE_ORDER


def test_status_transition_sent_to_cancelled_clears_on_order(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item 3",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-3",
            status=POStatusEnum.DRAFT,
            total_amount=700,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=7, unit_cost=100)],
        ),
    )

    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))
    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.CANCELLED))

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 0


def test_status_transition_received_to_returned_creates_stock_movement(db_session, seed_workspace, event_bus):
    """Verifies that transitioning from RECEIVED to RETURNED deducts stock via movement."""
    service = PurchaseOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Return",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-RET-1",
            status=POStatusEnum.DRAFT,
            total_amount=1000,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=20, unit_cost=50)],
        ),
    )
    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))
    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.RECEIVED))

    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.RETURNED))

    movements = inv_service.get_stock_movements(seed_workspace, item_id=item.id)
    assert movements.total == 2  # 1 for Received (+20), 1 for Returned (-20)

    returned_movement = sorted(movements.items, key=lambda x: x.created_at, reverse=True)[0]
    assert returned_movement.quantity_change == -20
    assert returned_movement.reference_type == OrderType.PURCHASE_ORDER


def test_status_transition_from_terminal_states_fails(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)

    po_rec = service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-T1", status=POStatusEnum.RECEIVED, purchase_order_lines=[])
    )
    po_can = service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-T2", status=POStatusEnum.CANCELLED, purchase_order_lines=[])
    )

    with pytest.raises(PurchaseOrderStatusTransitionError):
        service.update_purchase_order(seed_workspace, po_rec.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))

    with pytest.raises(PurchaseOrderStatusTransitionError):
        service.update_purchase_order(seed_workspace, po_can.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))


def test_status_transition_with_non_inventory_line(db_session, seed_workspace, event_bus):
    """Skipping inventory updates for lines without an item_id."""
    service = PurchaseOrderService(db_session, event_bus)
    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-65",
            status=POStatusEnum.DRAFT,
            total_amount=100,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=None, quantity=2, unit_cost=50)],
        ),
    )
    updated = service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))
    assert updated.status == POStatusEnum.SENT


# ==============================================================================
# 3. PURCHASE ORDER LINE TESTS (Handled via PurchaseOrderService Aggregate Root)
# ==============================================================================


def test_add_line_recalculates_total(db_session, seed_workspace, event_bus):
    po_service = PurchaseOrderService(db_session, event_bus)

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(po_number="PO-LINE-1", status=POStatusEnum.DRAFT, purchase_order_lines=[]),
    )

    po_service.add_line(seed_workspace, po.id, PurchaseOrderLineCreate(item_id=None, quantity=10, unit_cost=15))

    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 150


def test_add_line_to_sent_order_adds_on_order_inventory(db_session, seed_workspace, event_bus):
    po_service = PurchaseOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Line",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    po = po_service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-LINE-2", status=POStatusEnum.SENT, purchase_order_lines=[])
    )

    po_service.add_line(seed_workspace, po.id, PurchaseOrderLineCreate(item_id=item.id, quantity=4, unit_cost=10))

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 4


def test_update_line_recalculates_total_and_inventory(db_session, seed_workspace, event_bus):
    po_service = PurchaseOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Update",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-LINE-3",
            status=POStatusEnum.SENT,
            total_amount=100,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=10, unit_cost=10)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    # Simulate initial draft->sent inventory adjustment since creation bypassed status transition
    inv_service.adjust_quantity_on_order(seed_workspace, item.id, 10)
    db_session.flush()

    po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(quantity=15, unit_cost=20),
    )

    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 300

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 15


def test_update_line_item_id_change_fails(db_session, seed_workspace, event_bus):
    """
    Verifies that changing the item_id on an existing
    line raises PurchaseOrderLineItemChangeError.
    """
    po_service = PurchaseOrderService(db_session, event_bus)

    item1 = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-1", title="I1", base_price=10, is_deleted=False)
    item2 = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-2", title="I2", base_price=20, is_deleted=False)
    db_session.add_all([item1, item2])
    db_session.flush()

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-CHANGE-ITEM",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item1.id, quantity=1, unit_cost=10)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    with pytest.raises(PurchaseOrderLineItemChangeError):
        po_service.update_line(
            seed_workspace, po.id, line_id, PurchaseOrderLineUpdate(item_id=item2.id, quantity=1, unit_cost=5000)
        )


def test_remove_line_recalculates_total(db_session, seed_workspace, event_bus):
    po_service = PurchaseOrderService(db_session, event_bus)

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-LINE-4",
            status=POStatusEnum.DRAFT,
            total_amount=500,
            purchase_order_lines=[
                PurchaseOrderLineCreate(quantity=2, unit_cost=100),
                PurchaseOrderLineCreate(quantity=3, unit_cost=100),
            ],
        ),
    )
    assert po.total_amount == 500
    line_id_to_delete = po.purchase_order_lines[0].id

    po_service.remove_line(seed_workspace, po.id, line_id_to_delete)

    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 300
    assert len(updated_po.purchase_order_lines) == 1


def test_remove_line_from_sent_order_removes_on_order_inventory(db_session, seed_workspace, event_bus):
    """Verifies that removing a line on a SENT PO correctly deducts the on-order inventory balance."""
    po_service = PurchaseOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Sent",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-LINE-5",
            status=POStatusEnum.SENT,
            total_amount=1000,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=10, unit_cost=100)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    inv_service.adjust_quantity_on_order(seed_workspace, item.id, 10)
    db_session.flush()

    po_service.remove_line(seed_workspace, po.id, line_id)

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 0


def test_line_service_line_not_found(db_session, seed_workspace, active_purchase_order, event_bus):
    """Verifies updating or removing a non-existent line raises PurchaseOrderLineNotFoundError or ValidationError."""
    po_service = PurchaseOrderService(db_session, event_bus)
    fake_line_id = uuid.uuid4()

    with pytest.raises((PurchaseOrderLineNotFoundError, ValidationError)):
        po_service.update_line(
            seed_workspace, active_purchase_order.id, fake_line_id, PurchaseOrderLineUpdate(quantity=2)
        )

    with pytest.raises(PurchaseOrderLineNotFoundError):
        po_service.remove_line(seed_workspace, active_purchase_order.id, fake_line_id)


def test_line_modifications_fail_on_terminal_status(db_session, seed_workspace, event_bus):
    """
    Verifies that adding, updating, or removing lines on a RECEIVED or CANCELLED
    order raises PurchaseOrderNotEditableError.
    """
    po_service = PurchaseOrderService(db_session, event_bus)

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-TERM-1",
            status=POStatusEnum.RECEIVED,
            total_amount=10,
            purchase_order_lines=[PurchaseOrderLineCreate(quantity=1, unit_cost=10)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    with pytest.raises(PurchaseOrderNotEditableError):
        po_service.add_link = po_service.add_line(
            seed_workspace, po.id, PurchaseOrderLineCreate(quantity=5, unit_cost=10)
        )

    with pytest.raises(PurchaseOrderNotEditableError):
        po_service.update_line(seed_workspace, po.id, line_id, PurchaseOrderLineUpdate(quantity=5, unit_cost=10))

    with pytest.raises(PurchaseOrderNotEditableError):
        po_service.remove_line(seed_workspace, po.id, line_id)


def test_update_line_same_quantity_no_inventory_change(db_session, seed_workspace, event_bus):
    """Covers updating a line on a SENT order where delta == 0 (only unit_cost changes)."""
    po_service = PurchaseOrderService(db_session, event_bus)
    inv_service = InventoryService(db_session)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Delta Zero",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.flush()

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-DELTA-0",
            status=POStatusEnum.SENT,
            total_amount=100,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=10, unit_cost=10)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    # Adjust initial inventory manually
    inv_service.adjust_quantity_on_order(seed_workspace, item.id, 10)
    db_session.flush()

    # Update ONLY unit_cost, quantity remains 10 (delta = 0).
    # Also pass the exact same item_id to cover the "item_id != line.item_id" False branch.
    po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(item_id=item.id, quantity=10, unit_cost=25),
    )

    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 250

    # Ensure inventory wasn't modified because delta was 0
    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 10


def test_line_modifications_on_sent_order_without_item_id(db_session, seed_workspace, event_bus):
    """Covers updating and removing a non-inventory line (item_id=None) on a SENT order."""
    po_service = PurchaseOrderService(db_session, event_bus)

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-NO-ITEM",
            status=POStatusEnum.SENT,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=None, quantity=1, unit_cost=50)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(item_id=None, quantity=5, unit_cost=50),
    )
    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 250

    po_service.remove_line(seed_workspace, po.id, line_id)
    final_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert final_po.total_amount == 0
    assert len(final_po.purchase_order_lines) == 0
