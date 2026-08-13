import uuid

import pytest

from src.erp.api.modules.inventory.enums import OrderType
from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.item.models import Item
from src.erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderExistsError,
    PurchaseOrderLineNotFoundError,
    PurchaseOrderNotFoundError,
)
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine
from src.erp.api.modules.purchase_order.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineUpdate,
    PurchaseOrderUpdate,
)
from src.erp.api.modules.purchase_order.service import PurchaseOrderLineService, PurchaseOrderService
from src.erp.api.modules.supplier.models import Supplier

# ==============================================================================
# FIXTURES
# ==============================================================================


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
        status="DRAFT",
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
# 1. PURCHASE ORDER SERVICE & TENANT ISOLATION TESTS
# ==============================================================================


def test_create_purchase_order_success(db_session, seed_workspace, active_supplier):
    service = PurchaseOrderService(db_session)
    payload = PurchaseOrderCreate(
        po_number="PO-100",
        supplier_id=active_supplier.id,
        status="DRAFT",
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


def test_create_purchase_order_duplicate_number_fails(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)
    payload = PurchaseOrderCreate(po_number="PO-DUP", status="DRAFT", purchase_order_lines=[])

    service.create_purchase_order(seed_workspace, payload)

    with pytest.raises(PurchaseOrderExistsError):
        service.create_purchase_order(seed_workspace, payload)


def test_create_purchase_order_cross_tenant_number_allowed(db_session, seed_workspace, alt_workspace):
    """Ensures two separate workspaces can use the same purchase order number."""
    service = PurchaseOrderService(db_session)
    payload = PurchaseOrderCreate(po_number="PO-SHARED", status="DRAFT", purchase_order_lines=[])

    service.create_purchase_order(seed_workspace, payload)
    cross_po = service.create_purchase_order(alt_workspace, payload)

    assert cross_po.workspace_id == alt_workspace
    assert cross_po.po_number == "PO-SHARED"


def test_get_purchase_orders_pagination_and_search(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)

    service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="APPLE-1", status="DRAFT", purchase_order_lines=[])
    )
    service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="APPLE-2", status="DRAFT", purchase_order_lines=[])
    )
    service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="BANANA-1", status="DRAFT", purchase_order_lines=[])
    )

    res = service.get_purchase_orders(seed_workspace, page=1, limit=2)
    assert len(res.items) == 2
    assert res.total >= 3

    search_res = service.get_purchase_orders(seed_workspace, search="APPLE")
    assert len(search_res.items) == 2


def test_update_purchase_order_duplicate_number_fails(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)
    po1 = service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-ONE", status="DRAFT", purchase_order_lines=[])
    )
    service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-TWO", status="DRAFT", purchase_order_lines=[])
    )

    with pytest.raises(PurchaseOrderExistsError):
        service.update_purchase_order(seed_workspace, po1.id, PurchaseOrderUpdate(po_number="PO-TWO"))


def test_get_purchase_order_not_found(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)
    with pytest.raises(PurchaseOrderNotFoundError):
        service.get_purchase_order(seed_workspace, uuid.uuid4())


def test_delete_purchase_order_not_found(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)
    with pytest.raises(PurchaseOrderNotFoundError):
        service.delete_purchase_order(seed_workspace, uuid.uuid4())


def test_get_purchase_order_tenant_isolation(db_session, alt_workspace, active_purchase_order):
    service = PurchaseOrderService(db_session)
    with pytest.raises(PurchaseOrderNotFoundError):
        service.get_purchase_order(alt_workspace, active_purchase_order.id)


def test_update_purchase_order_basic_metadata(db_session, seed_workspace, active_purchase_order):
    service = PurchaseOrderService(db_session)
    update_payload = PurchaseOrderUpdate(po_number="PO-NEW-NUM")

    updated = service.update_purchase_order(seed_workspace, active_purchase_order.id, update_payload)
    assert updated.po_number == "PO-NEW-NUM"


def test_delete_purchase_order_soft_delete(db_session, seed_workspace, active_purchase_order):
    service = PurchaseOrderService(db_session)
    service.delete_purchase_order(seed_workspace, active_purchase_order.id)

    with pytest.raises(PurchaseOrderNotFoundError):
        service.get_purchase_order(seed_workspace, active_purchase_order.id)


def test_status_transition_with_non_inventory_line(db_session, seed_workspace):
    """Skipping inventory updates for lines without an item_id."""
    service = PurchaseOrderService(db_session)
    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-65",
            status="DRAFT",
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=None, quantity=2, unit_cost=50)],
        ),
    )
    updated = service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status="SENT"))
    assert updated.status == "SENT"


def test_status_transition_fallback_case(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)

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

    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-98",
            status="DRAFT",
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=1, unit_cost=100)],
        ),
    )

    updated = service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status="CANCELLED"))
    assert updated.status == "CANCELLED"


def test_delete_purchase_order_with_lines_cascades_soft_delete(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)
    po = service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-179",
            status="DRAFT",
            purchase_order_lines=[PurchaseOrderLineCreate(quantity=1, unit_cost=100)],
        ),
    )
    service.delete_purchase_order(seed_workspace, po.id)

    with pytest.raises(PurchaseOrderNotFoundError):
        service.get_purchase_order(seed_workspace, po.id)


# ==============================================================================
# 2. STATUS TRANSITIONS & INVENTORY LEDGER TESTS
# ==============================================================================


def test_status_transition_draft_to_sent_adds_on_order(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)
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
            status="DRAFT",
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=10, unit_cost=50)],
        ),
    )

    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status="SENT"))

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 10


def test_status_transition_sent_to_received_creates_stock_movement(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)
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
            status="DRAFT",
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=5, unit_cost=50)],
        ),
    )

    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status="SENT"))
    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status="RECEIVED"))

    inv_updated = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_on_order == 0

    movements = inv_service.get_stock_movements(seed_workspace, item_id=item.id)
    assert movements.total == 1
    assert movements.items[0].quantity_change == 5
    assert movements.items[0].reference_type == OrderType.PURCHASE_ORDER


def test_status_transition_sent_to_cancelled_clears_on_order(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)
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
            status="DRAFT",
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=7, unit_cost=100)],
        ),
    )

    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status="SENT"))
    service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status="CANCELLED"))

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 0


def test_status_transition_from_terminal_states_fails(db_session, seed_workspace):
    service = PurchaseOrderService(db_session)

    po_rec = service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-T1", status="RECEIVED", purchase_order_lines=[])
    )
    po_can = service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-T2", status="CANCELLED", purchase_order_lines=[])
    )

    with pytest.raises(ValueError):
        service.update_purchase_order(seed_workspace, po_rec.id, PurchaseOrderUpdate(status="SENT"))

    with pytest.raises(ValueError):
        service.update_purchase_order(seed_workspace, po_can.id, PurchaseOrderUpdate(status="SENT"))


# ==============================================================================
# 3. PURCHASE ORDER LINE SERVICE TESTS
# ==============================================================================


def test_add_line_recalculates_total(db_session, seed_workspace):
    po_service = PurchaseOrderService(db_session)
    line_service = PurchaseOrderLineService(db_session)

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(po_number="PO-LINE-1", status="DRAFT", purchase_order_lines=[]),
    )

    line_service.add_line(seed_workspace, po.id, PurchaseOrderLineCreate(item_id=None, quantity=10, unit_cost=15))

    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 150


def test_add_line_to_sent_order_adds_on_order_inventory(db_session, seed_workspace):
    po_service = PurchaseOrderService(db_session)
    line_service = PurchaseOrderLineService(db_session)
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
        seed_workspace, PurchaseOrderCreate(po_number="PO-LINE-2", status="SENT", purchase_order_lines=[])
    )

    line_service.add_line(seed_workspace, po.id, PurchaseOrderLineCreate(item_id=item.id, quantity=4, unit_cost=10))

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 4


def test_update_line_recalculates_total_and_inventory(db_session, seed_workspace):
    po_service = PurchaseOrderService(db_session)
    line_service = PurchaseOrderLineService(db_session)
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
            status="SENT",
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=10, unit_cost=10)],
        ),
    )
    line_id = po.purchase_order_lines[0].id
    inv_service.adjust_quantity_on_order(seed_workspace, item.id, 10)
    db_session.flush()

    line_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(quantity=15, unit_cost=20),
    )

    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 300

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 15


def test_remove_line_recalculates_total(db_session, seed_workspace):
    po_service = PurchaseOrderService(db_session)
    line_service = PurchaseOrderLineService(db_session)

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-LINE-4",
            status="DRAFT",
            purchase_order_lines=[
                PurchaseOrderLineCreate(quantity=2, unit_cost=100),
                PurchaseOrderLineCreate(quantity=3, unit_cost=100),
            ],
        ),
    )
    assert po.total_amount == 500
    line_id_to_delete = po.purchase_order_lines[0].id

    line_service.remove_line(seed_workspace, po.id, line_id_to_delete)

    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 300
    assert len(updated_po.purchase_order_lines) == 1


def test_remove_line_from_sent_order_removes_on_order_inventory(db_session, seed_workspace):
    po_service = PurchaseOrderService(db_session)
    line_service = PurchaseOrderLineService(db_session)
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
            status="SENT",
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=8, unit_cost=10)],
        ),
    )
    line_id = po.purchase_order_lines[0].id
    inv_service.adjust_quantity_on_order(seed_workspace, item.id, 8)
    db_session.flush()

    line_service.remove_line(seed_workspace, po.id, line_id)

    inv = inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 0


def test_modify_line_on_terminal_po_fails(db_session, seed_workspace):
    po_service = PurchaseOrderService(db_session)
    line_service = PurchaseOrderLineService(db_session)

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-LINE-6",
            status="RECEIVED",
            purchase_order_lines=[PurchaseOrderLineCreate(quantity=1, unit_cost=10)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    with pytest.raises(ValueError):
        line_service.add_line(seed_workspace, po.id, PurchaseOrderLineCreate(quantity=1, unit_cost=10))

    with pytest.raises(ValueError):
        line_service.update_line(seed_workspace, po.id, line_id, PurchaseOrderLineUpdate(quantity=5))

    with pytest.raises(ValueError):
        line_service.remove_line(seed_workspace, po.id, line_id)


def test_purchase_order_line_not_found_errors(db_session, seed_workspace, active_purchase_order):
    line_service = PurchaseOrderLineService(db_session)

    # Parent purchase order not found when adding line
    with pytest.raises(PurchaseOrderNotFoundError):
        line_service.add_line(seed_workspace, uuid.uuid4(), PurchaseOrderLineCreate(quantity=1, unit_cost=10))

    # Line not found when updating
    with pytest.raises(PurchaseOrderLineNotFoundError):
        line_service.update_line(
            seed_workspace, active_purchase_order.id, uuid.uuid4(), PurchaseOrderLineUpdate(quantity=5, unit_cost=10)
        )

    # Line not found when removing
    with pytest.raises(PurchaseOrderLineNotFoundError):
        line_service.remove_line(seed_workspace, active_purchase_order.id, uuid.uuid4())


def test_update_line_on_draft_order_recalculates_total_only(db_session, seed_workspace):
    po_service = PurchaseOrderService(db_session)
    line_service = PurchaseOrderLineService(db_session)

    po = po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-DRAFT-LINE",
            status="DRAFT",
            purchase_order_lines=[PurchaseOrderLineCreate(quantity=2, unit_cost=100)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    updated_line = line_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(quantity=5, unit_cost=100),
    )
    assert updated_line.quantity == 5

    updated_po = po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 500


def test_purchase_order_line_cross_tenant_isolation_fails(db_session, alt_workspace, active_purchase_order):
    line_service = PurchaseOrderLineService(db_session)

    with pytest.raises(PurchaseOrderNotFoundError):
        line_service.add_line(
            alt_workspace, active_purchase_order.id, PurchaseOrderLineCreate(quantity=1, unit_cost=10)
        )
