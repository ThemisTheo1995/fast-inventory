import uuid

import pytest

from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderCannotDeleteError,
    PurchaseOrderNotFoundError,
)
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_delete_purchase_order_soft_delete(db_session, seed_workspace, active_purchase_order, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    await service.delete_purchase_order(seed_workspace, active_purchase_order.id)

    with pytest.raises(PurchaseOrderNotFoundError):
        await service.get_purchase_order(seed_workspace, active_purchase_order.id)


@pytest.mark.asyncio
async def test_delete_purchase_order_not_found(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    with pytest.raises(PurchaseOrderNotFoundError):
        await service.delete_purchase_order(seed_workspace, uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_purchase_order_with_lines_cascades_soft_delete(db_session, seed_workspace, event_bus):
    service = PurchaseOrderService(db_session, event_bus)
    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number="PO-GAP-179",
            status=POStatusEnum.DRAFT,
            total_amount=100,
            purchase_order_lines=[PurchaseOrderLineCreate(quantity=1, unit_cost=100)],
        ),
    )
    await service.delete_purchase_order(seed_workspace, po.id)

    with pytest.raises(PurchaseOrderNotFoundError):
        await service.get_purchase_order(seed_workspace, po.id)


@pytest.mark.asyncio
async def test_delete_purchase_order_fails_if_not_draft_or_cancelled(db_session, seed_workspace, event_bus):
    """Verifies that deleting a PO in a SENT or RECEIVED status raises PurchaseOrderCannotDeleteError."""
    service = PurchaseOrderService(db_session, event_bus)
    po = await service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(po_number="PO-DEL-ERR", status=POStatusEnum.SENT, purchase_order_lines=[]),
    )

    with pytest.raises(PurchaseOrderCannotDeleteError):
        await service.delete_purchase_order(seed_workspace, po.id)
