import uuid

import pytest
from sqlalchemy import select

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
async def test_update_purchase_order_basic_metadata(
    db_session,
    seed_workspace,
    active_purchase_order,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    update_payload = PurchaseOrderUpdate(po_number="PO-NEW-NUM")

    updated = await service.update_purchase_order(
        seed_workspace,
        active_purchase_order.id,
        update_payload,
    )

    assert updated.po_number == "PO-NEW-NUM"


@pytest.mark.asyncio
async def test_update_purchase_order_duplicate_number_fails(
    db_session,
    seed_workspace,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    po1 = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-ONE",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[],
        ),
    )

    await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-TWO",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[],
        ),
    )

    with pytest.raises(PurchaseOrderExistsError):
        await service.update_purchase_order(
            seed_workspace,
            po1.id,
            PurchaseOrderUpdate(po_number="PO-TWO"),
        )


@pytest.mark.asyncio
async def test_update_purchase_order_same_number_allowed(
    db_session,
    seed_workspace,
    event_bus,
):
    """Updating a PO without changing its number should be allowed."""

    service = PurchaseOrderService(db_session, event_bus)

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-SAME-NUM",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[],
        ),
    )

    updated_po = await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(
            po_number="PO-SAME-NUM",
            status=POStatusEnum.SENT,
        ),
    )

    assert updated_po.po_number == "PO-SAME-NUM"
    assert updated_po.status == POStatusEnum.SENT


@pytest.mark.asyncio
async def test_status_transition_draft_to_sent_adds_on_order_quantity(
    db_session,
    seed_workspace,
    event_bus,
):
    """Transitioning from DRAFT to SENT increases Item.quantity_on_order."""

    service = PurchaseOrderService(db_session, event_bus)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item",
        base_price=100,
        quantity_on_order=0,
        quantity_allocated=0,
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.flush()

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-1",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=item.id,
                    quantity=10,
                    unit_cost=50,
                )
            ],
        ),
    )

    updated_po = await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.SENT),
    )

    result = await db_session.execute(select(Item.quantity_on_order).where(Item.id == item.id))

    assert updated_po.status == POStatusEnum.SENT
    assert result.scalar_one() == 10


@pytest.mark.asyncio
async def test_status_transition_sent_to_received_reduces_on_order_quantity(
    db_session,
    seed_workspace,
    event_bus,
):
    """
    Receiving a PO reduces quantity_on_order.

    The current received handler does not create physical stock movements.
    """

    service = PurchaseOrderService(db_session, event_bus)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Received",
        base_price=100,
        quantity_on_order=0,
        quantity_allocated=0,
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.flush()

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-2",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=item.id,
                    quantity=5,
                    unit_cost=50,
                )
            ],
        ),
    )

    await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.SENT),
    )

    received_po = await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.RECEIVED),
    )

    result = await db_session.execute(select(Item.quantity_on_order).where(Item.id == item.id))

    assert received_po.status == POStatusEnum.RECEIVED
    assert result.scalar_one() == 0


@pytest.mark.asyncio
async def test_status_transition_sent_to_cancelled_clears_on_order_quantity(
    db_session,
    seed_workspace,
    event_bus,
):
    """Cancelling a SENT PO reduces its on-order quantity to zero."""

    service = PurchaseOrderService(db_session, event_bus)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Cancelled",
        base_price=100,
        quantity_on_order=0,
        quantity_allocated=0,
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.flush()

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-STATE-3",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=item.id,
                    quantity=7,
                    unit_cost=100,
                )
            ],
        ),
    )

    await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.SENT),
    )

    cancelled_po = await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.CANCELLED),
    )

    result = await db_session.execute(select(Item.quantity_on_order).where(Item.id == item.id))

    assert cancelled_po.status == POStatusEnum.CANCELLED
    assert result.scalar_one() == 0


@pytest.mark.asyncio
async def test_status_transition_received_to_returned_does_not_change_on_order_quantity(
    db_session,
    seed_workspace,
    event_bus,
):
    """
    The current RETURNED handler is a no-op.

    Returning a received PO does not create a stock movement or change
    Item.quantity_on_order under the current implementation.
    """

    service = PurchaseOrderService(db_session, event_bus)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Return",
        base_price=100,
        quantity_on_order=0,
        quantity_allocated=0,
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.flush()

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-RET-1",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=item.id,
                    quantity=20,
                    unit_cost=50,
                )
            ],
        ),
    )

    await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.SENT),
    )

    await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.RECEIVED),
    )

    returned_po = await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.RETURNED),
    )

    result = await db_session.execute(select(Item.quantity_on_order).where(Item.id == item.id))

    assert returned_po.status == POStatusEnum.RETURNED
    assert result.scalar_one() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "initial_status",
    [
        POStatusEnum.RECEIVED,
        POStatusEnum.CANCELLED,
        POStatusEnum.RETURNED,
        POStatusEnum.CLOSED,
    ],
)
async def test_status_transition_from_terminal_states_fails(
    db_session,
    seed_workspace,
    event_bus,
    initial_status,
):
    """Statuses without an allowed outgoing transition cannot transition to SENT."""

    service = PurchaseOrderService(db_session, event_bus)

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number=f"PO-INVALID-{initial_status.value}",
            status=initial_status,
            purchase_order_lines=[],
        ),
    )

    with pytest.raises(PurchaseOrderStatusTransitionError):
        await service.update_purchase_order(
            seed_workspace,
            po.id,
            PurchaseOrderUpdate(status=POStatusEnum.SENT),
        )


@pytest.mark.asyncio
async def test_status_transition_with_non_inventory_line(
    db_session,
    seed_workspace,
    event_bus,
):
    """A line without item_id does not trigger an item quantity adjustment."""

    service = PurchaseOrderService(db_session, event_bus)

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-65",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=None,
                    quantity=2,
                    unit_cost=50,
                )
            ],
        ),
    )

    updated = await service.update_purchase_order(
        seed_workspace,
        po.id,
        PurchaseOrderUpdate(status=POStatusEnum.SENT),
    )

    assert updated.status == POStatusEnum.SENT
