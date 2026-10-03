import uuid

import pytest

from erp.api.modules.inventory.enums import OrderType
from erp.api.modules.inventory.service import InventoryService
from erp.api.modules.item.models import Item
from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderExistsError,
    PurchaseOrderStatusTransitionError,
)
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderUpdate,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_update_purchase_order_basic_metadata(db_session, seed_workspace, active_purchase_order, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    update_payload = PurchaseOrderUpdate(po_number="PO-NEW-NUM")

    updated = await service.update_purchase_order(seed_workspace, active_purchase_order.id, update_payload)
    assert updated.po_number == "PO-NEW-NUM"


@pytest.mark.asyncio
async def test_update_purchase_order_duplicate_number_fails(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    po1 = await service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-ONE", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )
    await service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-TWO", status=POStatusEnum.DRAFT, purchase_order_lines=[])
    )

    with pytest.raises(PurchaseOrderExistsError):
        await service.update_purchase_order(seed_workspace, po1.id, PurchaseOrderUpdate(po_number="PO-TWO"))


@pytest.mark.asyncio
async def test_update_purchase_order_same_number_allowed(db_session, seed_workspace, event_bus):
    """Verifies that updating a PO without changing its po_number does not trigger a unique constraint error."""
    service = PurchaseOrderService(db_session, event_bus)
    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(po_number="PO-SAME-NUM", status=POStatusEnum.DRAFT, purchase_order_lines=[]),
    )

    updated_po = await service.update_purchase_order(
        seed_workspace, po.id, PurchaseOrderUpdate(po_number="PO-SAME-NUM", status=POStatusEnum.SENT)
    )
    assert updated_po.status == POStatusEnum.SENT


@pytest.mark.asyncio
async def test_status_transition_draft_to_sent_adds_on_order(db_session, seed_workspace, event_bus):
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
    await db_session.flush()

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-1",
            status=POStatusEnum.DRAFT,
            total_amount=500,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=10, unit_cost=50)],
        ),
    )

    await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 10


@pytest.mark.asyncio
async def test_status_transition_sent_to_received_creates_stock_movement(db_session, seed_workspace, event_bus):
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
    await db_session.flush()

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-2",
            status=POStatusEnum.DRAFT,
            total_amount=250,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=5, unit_cost=50)],
        ),
    )

    await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))
    await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.RECEIVED))

    inv_updated = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv_updated.quantity_on_order == 0

    movements = await inv_service.get_stock_movements(seed_workspace, item_id=item.id)
    assert movements.total == 1
    assert movements.items[0].quantity_change == 5
    assert movements.items[0].reference_type == OrderType.PURCHASE_ORDER


@pytest.mark.asyncio
async def test_status_transition_sent_to_cancelled_clears_on_order(db_session, seed_workspace, event_bus):
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
    await db_session.flush()

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-3",
            status=POStatusEnum.DRAFT,
            total_amount=700,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=7, unit_cost=100)],
        ),
    )

    await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))
    await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.CANCELLED))

    inv = await inv_service.get_inventory_by_item(seed_workspace, item.id)
    assert inv.quantity_on_order == 0


@pytest.mark.asyncio
async def test_status_transition_received_to_returned_creates_stock_movement(db_session, seed_workspace, event_bus):
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
    await db_session.flush()

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-RET-1",
            status=POStatusEnum.DRAFT,
            total_amount=1000,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=item.id, quantity=20, unit_cost=50)],
        ),
    )
    await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))
    await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.RECEIVED))

    await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.RETURNED))

    movements = await inv_service.get_stock_movements(seed_workspace, item_id=item.id)
    assert movements.total == 2  # 1 for Received (+20), 1 for Returned (-20)

    returned_movement = sorted(movements.items, key=lambda x: x.created_at, reverse=True)[0]
    assert returned_movement.quantity_change == -20
    assert returned_movement.reference_type == OrderType.PURCHASE_ORDER


@pytest.mark.asyncio
async def test_status_transition_from_terminal_states_fails(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)

    po_rec = await service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-T1", status=POStatusEnum.RECEIVED, purchase_order_lines=[])
    )
    po_can = await service.create_purchase_order(
        seed_workspace, PurchaseOrderCreate(po_number="PO-T2", status=POStatusEnum.CANCELLED, purchase_order_lines=[])
    )

    with pytest.raises(PurchaseOrderStatusTransitionError):
        await service.update_purchase_order(seed_workspace, po_rec.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))

    with pytest.raises(PurchaseOrderStatusTransitionError):
        await service.update_purchase_order(seed_workspace, po_can.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))


@pytest.mark.asyncio
async def test_status_transition_with_non_inventory_line(db_session, seed_workspace, event_bus):
    """Skipping inventory updates for lines without an item_id."""
    service = PurchaseOrderService(db_session, event_bus)
    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-65",
            status=POStatusEnum.DRAFT,
            total_amount=100,
            purchase_order_lines=[PurchaseOrderLineCreate(item_id=None, quantity=2, unit_cost=50)],
        ),
    )
    updated = await service.update_purchase_order(seed_workspace, po.id, PurchaseOrderUpdate(status=POStatusEnum.SENT))
    assert updated.status == POStatusEnum.SENT
