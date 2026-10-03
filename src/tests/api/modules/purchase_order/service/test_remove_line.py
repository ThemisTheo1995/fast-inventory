import uuid

import pytest

from erp.api.modules.inventory.service import InventoryService
from erp.api.modules.item.models import Item
from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderLineNotFoundError,
    PurchaseOrderNotEditableError,
)
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_remove_line_recalculates_total(db_session, seed_workspace, event_bus):
    po_service = PurchaseOrderService(db_session, event_bus)

    po = await po_service.create_purchase_order(
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

    await po_service.remove_line(seed_workspace, po.id, line_id_to_delete)

    updated_po = await po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 300
    assert len(updated_po.purchase_order_lines) == 1


@pytest.mark.asyncio
async def test_remove_line_from_sent_order_removes_on_order_inventory(db_session, seed_workspace, event_bus):
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
    await db_session.flush()

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-LINE-5",
            status=POStatusEnum.SENT,
            total_amount=1000,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=10, unit_cost=100)],
        ),
    )
    line_id = po.purchase_order_lines[0].id

    await inv_service.adjust_quantity_on_order(seed_workspace, item.id, 10)
    await db_session.flush()

    await po_service.remove_line(seed_workspace, po.id, line_id)

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 0


@pytest.mark.asyncio
async def test_line_service_line_not_found(db_session, seed_workspace, active_purchase_order, event_bus):
    """Verifies removing a non-existent line raises PurchaseOrderLineNotFoundError or ValidationError."""
    po_service = PurchaseOrderService(db_session, event_bus)
    fake_line_id = uuid.uuid4()

    with pytest.raises(PurchaseOrderLineNotFoundError):
        await po_service.remove_line(seed_workspace, active_purchase_order.id, fake_line_id)


@pytest.mark.asyncio
async def test_line_modifications_on_sent_order_without_item_id(db_session, seed_workspace, event_bus):
    """Covers removing a non-inventory line (item_id=None) on a SENT order."""
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

    await po_service.remove_line(seed_workspace, po.id, line_id)
    final_po = await po_service.get_purchase_order(seed_workspace, po.id)
    assert final_po.total_amount == 0
    assert len(final_po.purchase_order_lines) == 0


@pytest.mark.asyncio
async def test_line_modifications_fail_on_terminal_status(db_session, seed_workspace, event_bus):
    """
    Verifies that removing lines on a RECEIVED or CANCELLED order raises PurchaseOrderNotEditableError.
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
        await po_service.remove_line(seed_workspace, po.id, line_id)
