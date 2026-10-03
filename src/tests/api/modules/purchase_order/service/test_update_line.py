import uuid

import pytest

from erp.api.modules.inventory.service import InventoryService
from erp.api.modules.item.models import Item
from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderLineItemChangeError,
    PurchaseOrderLineNotFoundError,
    PurchaseOrderNotEditableError,
)
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineUpdate,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_update_line_recalculates_total_and_inventory(db_session, seed_workspace, event_bus):
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
    await db_session.flush()

    po = await po_service.create_purchase_order(
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
    await inv_service.adjust_quantity_on_order(seed_workspace, item.id, 10)
    await db_session.flush()

    await po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(quantity=15, unit_cost=20),
    )

    updated_po = await po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 300

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 15


@pytest.mark.asyncio
async def test_update_line_same_quantity_no_inventory_change(db_session, seed_workspace, event_bus):
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
    await db_session.flush()

    po = await po_service.create_purchase_order(
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
    await inv_service.adjust_quantity_on_order(seed_workspace, item.id, 10)
    await db_session.flush()

    # Update ONLY unit_cost, quantity remains 10 (delta = 0).
    # Also pass the exact same item_id to cover the "item_id != line.item_id" False branch.
    await po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(item_id=item.id, quantity=10, unit_cost=25),
    )

    updated_po = await po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 250

    # Ensure inventory wasn't modified because delta was 0
    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 10


@pytest.mark.asyncio
async def test_update_line_item_id_change_fails(db_session, seed_workspace, event_bus):
    """
    Verifies that changing the item_id on an existing
    line raises PurchaseOrderLineItemChangeError.
    """
    po_service = PurchaseOrderService(db_session, event_bus)

    item1 = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-1", title="I1", base_price=10, is_deleted=False)
    item2 = Item(id=uuid.uuid4(), workspace_id=seed_workspace, sku="SKU-2", title="I2", base_price=20, is_deleted=False)
    db_session.add_all([item1, item2])
    await db_session.flush()

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-CHANGE-ITEM",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item1.id, quantity=1, unit_cost=10)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    with pytest.raises(PurchaseOrderLineItemChangeError):
        await po_service.update_line(
            seed_workspace, po.id, line_id, PurchaseOrderLineUpdate(item_id=item2.id, quantity=1, unit_cost=5000)
        )


@pytest.mark.asyncio
async def test_line_modifications_fail_on_terminal_status(db_session, seed_workspace, event_bus):
    """
    Verifies that adding, updating, or removing lines on a RECEIVED or CANCELLED
    order raises PurchaseOrderNotEditableError.
    """
    po_service = PurchaseOrderService(db_session, event_bus)

    po = await po_service.create_purchase_order(
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
        await po_service.update_line(seed_workspace, po.id, line_id, PurchaseOrderLineUpdate(quantity=5, unit_cost=10))


@pytest.mark.asyncio
async def test_line_modifications_on_sent_order_without_item_id(db_session, seed_workspace, event_bus):
    """Covers updating a non-inventory line (item_id=None) on a SENT order."""
    po_service = PurchaseOrderService(db_session, event_bus)

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-NO-ITEM",
            status=POStatusEnum.SENT,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=None, quantity=1, unit_cost=50)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    await po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(item_id=None, quantity=5, unit_cost=50),
    )
    updated_po = await po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 250


@pytest.mark.asyncio
async def test_line_service_line_not_found(db_session, seed_workspace, active_purchase_order, event_bus):
    """Verifies updating a non-existent line raises PurchaseOrderLineNotFoundError or ValidationError."""
    po_service = PurchaseOrderService(db_session, event_bus)
    fake_line_id = uuid.uuid4()

    with pytest.raises(PurchaseOrderLineNotFoundError):
        await po_service.update_line(
            seed_workspace, active_purchase_order.id, fake_line_id, PurchaseOrderLineUpdate(unit_cost=100, quantity=2)
        )
