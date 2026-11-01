import uuid

import pytest
from sqlalchemy import select

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
async def test_update_line_recalculates_total_and_on_order_quantity(
    db_session,
    seed_workspace,
    event_bus,
):
    po_service = PurchaseOrderService(db_session, event_bus)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Update",
        base_price=100,
        quantity_on_order=0,
        quantity_allocated=0,
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.flush()

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-LINE-3",
            status=POStatusEnum.SENT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=item.id,
                    quantity=10,
                    unit_cost=10,
                )
            ],
        ),
    )

    line_id = po.purchase_order_lines[0].id

    # The PO was created directly as SENT, so its transition event
    # was not published. Seed the existing on-order balance.
    item.quantity_on_order = 10
    await db_session.flush()

    await po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(
            quantity=15,
            unit_cost=20,
        ),
    )

    updated_po = await po_service.get_purchase_order(
        seed_workspace,
        po.id,
    )

    assert updated_po.total_amount == 300

    result = await db_session.execute(
        select(Item.quantity_on_order).where(
            Item.id == item.id,
            Item.workspace_id == seed_workspace,
        )
    )

    assert result.scalar_one() == 15


@pytest.mark.asyncio
async def test_update_line_same_quantity_no_on_order_change(
    db_session,
    seed_workspace,
    event_bus,
):
    """Changing only unit_cost must not change quantity_on_order."""

    po_service = PurchaseOrderService(db_session, event_bus)

    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Test Item Delta Zero",
        base_price=100,
        quantity_on_order=10,
        quantity_allocated=0,
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.flush()

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-DELTA-0",
            status=POStatusEnum.SENT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=item.id,
                    quantity=10,
                    unit_cost=10,
                )
            ],
        ),
    )

    line_id = po.purchase_order_lines[0].id

    await po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(
            item_id=item.id,
            quantity=10,
            unit_cost=25,
        ),
    )

    updated_po = await po_service.get_purchase_order(
        seed_workspace,
        po.id,
    )

    assert updated_po.total_amount == 250

    result = await db_session.execute(
        select(Item.quantity_on_order).where(
            Item.id == item.id,
            Item.workspace_id == seed_workspace,
        )
    )

    assert result.scalar_one() == 10


@pytest.mark.asyncio
async def test_update_line_item_id_change_fails(
    db_session,
    seed_workspace,
    event_bus,
):
    """Changing the item_id of an existing PO line is not permitted."""

    po_service = PurchaseOrderService(db_session, event_bus)

    item1 = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Item 1",
        base_price=10,
        is_deleted=False,
    )
    item2 = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Item 2",
        base_price=20,
        is_deleted=False,
    )

    db_session.add_all([item1, item2])
    await db_session.flush()

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-CHANGE-ITEM",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=item1.id,
                    quantity=1,
                    unit_cost=10,
                )
            ],
        ),
    )

    line_id = po.purchase_order_lines[0].id

    with pytest.raises(PurchaseOrderLineItemChangeError):
        await po_service.update_line(
            seed_workspace,
            po.id,
            line_id,
            PurchaseOrderLineUpdate(
                item_id=item2.id,
                quantity=1,
                unit_cost=5000,
            ),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        POStatusEnum.RECEIVED,
        POStatusEnum.CANCELLED,
        POStatusEnum.RETURNED,
    ],
)
async def test_line_modifications_fail_on_terminal_status(
    db_session,
    seed_workspace,
    event_bus,
    status,
):
    """Updating a line on a non-editable PO status raises an error."""

    po_service = PurchaseOrderService(db_session, event_bus)

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number=f"PO-TERM-{status.value}",
            status=status,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    quantity=1,
                    unit_cost=10,
                )
            ],
        ),
    )

    line_id = po.purchase_order_lines[0].id

    with pytest.raises(PurchaseOrderNotEditableError):
        await po_service.update_line(
            seed_workspace,
            po.id,
            line_id,
            PurchaseOrderLineUpdate(
                quantity=5,
                unit_cost=10,
            ),
        )


@pytest.mark.asyncio
async def test_update_line_on_sent_order_without_item_id(
    db_session,
    seed_workspace,
    event_bus,
):
    """Updating a non-inventory line recalculates the PO total."""

    po_service = PurchaseOrderService(db_session, event_bus)

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-NO-ITEM",
            status=POStatusEnum.SENT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(
                    item_id=None,
                    quantity=1,
                    unit_cost=50,
                )
            ],
        ),
    )

    line_id = po.purchase_order_lines[0].id

    await po_service.update_line(
        seed_workspace,
        po.id,
        line_id,
        PurchaseOrderLineUpdate(
            item_id=None,
            quantity=5,
            unit_cost=50,
        ),
    )

    updated_po = await po_service.get_purchase_order(
        seed_workspace,
        po.id,
    )

    assert updated_po.total_amount == 250
    assert updated_po.purchase_order_lines[0].quantity == 5


@pytest.mark.asyncio
async def test_line_service_line_not_found(
    db_session,
    seed_workspace,
    active_purchase_order,
    event_bus,
):
    """Updating a non-existent line raises PurchaseOrderLineNotFoundError."""

    po_service = PurchaseOrderService(db_session, event_bus)
    fake_line_id = uuid.uuid4()

    with pytest.raises(PurchaseOrderLineNotFoundError):
        await po_service.update_line(
            seed_workspace,
            active_purchase_order.id,
            fake_line_id,
            PurchaseOrderLineUpdate(
                unit_cost=100,
                quantity=2,
            ),
        )
