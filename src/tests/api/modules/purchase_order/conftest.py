import uuid

import pytest

from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine
from src.erp.api.modules.supplier.models import Supplier

# --- SUPPLIER FIXTURES ---


@pytest.fixture
async def active_supplier(db_session, seed_workspace) -> Supplier:
    """Seeds a live supplier record attached to the primary workspace."""
    supplier = Supplier(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        name="Active Supplier",
        email="active.supplier@test.com",
        is_deleted=False,
    )
    db_session.add(supplier)
    await db_session.commit()
    await db_session.refresh(supplier)
    return supplier


# --- PURCHASE ORDER FIXTURES ---


@pytest.fixture
async def active_purchase_order(db_session, seed_workspace, active_supplier) -> PurchaseOrder:
    """Seeds a live purchase order record attached to the primary workspace and active supplier."""
    purchase_order = PurchaseOrder(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        supplier_id=active_supplier.id,
        po_number="PO-FIXTURE-001",
        total_amount=1250,  # Arbitrary fixture amount
        status="DRAFT",
    )
    db_session.add(purchase_order)
    await db_session.commit()
    await db_session.refresh(purchase_order)
    return purchase_order


@pytest.fixture
async def active_purchase_order_line(db_session, active_purchase_order) -> PurchaseOrderLine:
    """Seeds a single purchase order line attached to the active_purchase_order."""
    purchase_order_line = PurchaseOrderLine(
        id=uuid.uuid4(),
        purchase_order_id=active_purchase_order.id,
        item_id=None,
        quantity=5,
        unit_cost=250,
    )
    db_session.add(purchase_order_line)
    await db_session.commit()
    await db_session.refresh(purchase_order_line)
    return purchase_order_line
