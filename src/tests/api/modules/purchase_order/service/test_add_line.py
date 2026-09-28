import uuid

import pytest

from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.item.models import Item
from src.erp.api.modules.purchase_order.enums import POStatusEnum
from src.erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from src.erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_add_line_recalculates_total(db_session, seed_workspace, event_bus):
    po_service = PurchaseOrderService(db_session, event_bus)

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(po_number="PO-LINE-1", status=POStatusEnum.DRAFT, purchase_order_lines=[]),
    )

    await po_service.add_line(seed_workspace, po.id, PurchaseOrderLineCreate(item_id=None, quantity=10, unit_cost=15))

    updated_po = await po_service.get_purchase_order(seed_workspace, po.id)
    assert updated_po.total_amount == 150


@pytest.mark.asyncio
async def test_add_line_to_sent_order_adds_on_order_inventory(db_session, seed_workspace, event_bus):
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
    await db_session.flush()

    po = await po_service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-LINE-2", status=POStatusEnum.SENT, purchase_order_lines=[])
    )

    await po_service.add_line(seed_workspace, po.id, PurchaseOrderLineCreate(item_id=item.id, quantity=4, unit_cost=10))

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 4
