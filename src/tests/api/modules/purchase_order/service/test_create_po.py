import pytest

from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderExistsError,
    PurchaseOrderNotEditableError,
)
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from erp.api.modules.purchase_order.service import PurchaseOrderService


@pytest.mark.asyncio
async def test_create_purchase_order_success(
    db_session,
    seed_workspace,
    active_supplier,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    payload = PurchaseOrderCreate(
        po_number="PO-100",
        supplier_id=active_supplier.id,
        status=POStatusEnum.DRAFT,
        purchase_order_lines=[
            PurchaseOrderLineCreate(quantity=2, unit_cost=500),
            PurchaseOrderLineCreate(quantity=3, unit_cost=100),
        ],
    )

    po = await service.create_purchase_order(seed_workspace, payload)

    assert po.id is not None
    assert po.po_number == "PO-100"
    assert po.total_amount == 1300
    assert po.workspace_id == seed_workspace
    assert po.supplier_id == active_supplier.id
    assert len(po.purchase_order_lines) == 2


@pytest.mark.asyncio
async def test_create_purchase_order_duplicate_number_fails(
    db_session,
    seed_workspace,
    event_bus,
):
    service = PurchaseOrderService(db_session, event_bus)

    payload = PurchaseOrderCreate(
        po_number="PO-DUP",
        status=POStatusEnum.DRAFT,
        purchase_order_lines=[],
    )

    await service.create_purchase_order(seed_workspace, payload)

    with pytest.raises(PurchaseOrderExistsError):
        await service.create_purchase_order(seed_workspace, payload)


@pytest.mark.asyncio
async def test_create_purchase_order_cross_tenant_number_allowed(
    db_session,
    seed_workspace,
    alt_workspace,
    event_bus,
):
    """Separate workspaces can use the same purchase order number."""
    service = PurchaseOrderService(db_session, event_bus)

    payload = PurchaseOrderCreate(
        po_number="PO-SHARED",
        status=POStatusEnum.DRAFT,
        purchase_order_lines=[],
    )

    await service.create_purchase_order(seed_workspace, payload)

    cross_po = await service.create_purchase_order(
        alt_workspace,
        payload,
    )

    assert cross_po.workspace_id == alt_workspace
    assert cross_po.po_number == "PO-SHARED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_status",
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
    terminal_status,
):
    """Terminal purchase orders cannot have lines added."""
    po_service = PurchaseOrderService(db_session, event_bus)

    po = await po_service.create_purchase_order(
        seed_workspace,
        PurchaseOrderCreate(
            po_number=f"PO-TERM-{terminal_status.value}",
            status=terminal_status,
            purchase_order_lines=[
                PurchaseOrderLineCreate(quantity=1, unit_cost=10),
            ],
        ),
    )

    with pytest.raises(PurchaseOrderNotEditableError):
        await po_service.add_line(
            seed_workspace,
            po.id,
            PurchaseOrderLineCreate(quantity=5, unit_cost=10),
        )
