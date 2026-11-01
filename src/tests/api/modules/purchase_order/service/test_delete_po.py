import uuid

import pytest
from sqlalchemy import select

from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderCannotDeleteError,
    PurchaseOrderNotFoundError,
)
from erp.api.modules.purchase_order.models import PurchaseOrderLine
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_delete_purchase_order_soft_delete(
    db_session,
    seed_workspace,
    active_purchase_order,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    await service.delete_purchase_order(
        seed_workspace,
        active_purchase_order.id,
    )

    with pytest.raises(PurchaseOrderNotFoundError):
        await service.get_purchase_order(
            seed_workspace,
            active_purchase_order.id,
        )


@pytest.mark.asyncio
async def test_delete_purchase_order_not_found(
    db_session,
    seed_workspace,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    with pytest.raises(PurchaseOrderNotFoundError):
        await service.delete_purchase_order(
            seed_workspace,
            uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_delete_purchase_order_with_lines_cascades_soft_delete(
    db_session,
    seed_workspace,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-179",
            status=POStatusEnum.DRAFT,
            purchase_order_lines=[
                PurchaseOrderLineCreate(quantity=1, unit_cost=100),
            ],
        ),
    )

    line_id = po.purchase_order_lines[0].id

    await service.delete_purchase_order(
        seed_workspace,
        po.id,
    )

    with pytest.raises(PurchaseOrderNotFoundError):
        await service.get_purchase_order(
            seed_workspace,
            po.id,
        )

    # Verify that the associated line was also soft-deleted.
    line = await db_session.scalar(
        select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == line_id,
        )
    )

    assert line is not None
    assert line.is_deleted is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_value",
    [
        POStatusEnum.SENT,
        POStatusEnum.RECEIVED,
        POStatusEnum.RETURNED,
    ],
)
async def test_delete_purchase_order_fails_if_not_draft_or_cancelled(
    db_session,
    seed_workspace,
    event_bus,
    status_value,
):
    service = PurchaseOrderService(db_session, event_bus)

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number=f"PO-DEL-{status_value.value}",
            status=status_value,
            purchase_order_lines=[],
        ),
    )

    with pytest.raises(PurchaseOrderCannotDeleteError):
        await service.delete_purchase_order(
            seed_workspace,
            po.id,
        )


@pytest.mark.asyncio
async def test_delete_cancelled_purchase_order_success(
    db_session,
    seed_workspace,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-DEL-CANCELLED",
            status=POStatusEnum.CANCELLED,
            purchase_order_lines=[],
        ),
    )

    await service.delete_purchase_order(seed_workspace, po.id)

    with pytest.raises(PurchaseOrderNotFoundError):
        await service.get_purchase_order(seed_workspace, po.id)
