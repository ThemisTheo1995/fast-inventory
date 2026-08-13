import uuid

import pytest

from src.erp.api.modules.customer.models import Customer
from src.erp.api.modules.sell_order.models import SellOrder, SellOrderLine

# --- CUSTOMER FIXTURES ---


@pytest.fixture
def active_customer(db_session, seed_workspace) -> Customer:
    """Seeds a live customer record attached to the primary workspace."""
    customer = Customer(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        first_name="Active",
        last_name="Customer",
        email="active.customer@test.com",
        is_deleted=False,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


# --- SELL ORDER FIXTURES ---


@pytest.fixture
def active_sell_order(db_session, seed_workspace, active_customer) -> SellOrder:
    """Seeds a live sell order record attached to the primary workspace and active customer."""
    sell_order = SellOrder(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        customer_id=active_customer.id,
        so_number="SO-FIXTURE-001",
        total_amount=1250,  # Arbitrary fixture amount
        status="DRAFT",
    )
    db_session.add(sell_order)
    db_session.commit()
    db_session.refresh(sell_order)
    return sell_order


@pytest.fixture
def active_sell_order_line(db_session, active_sell_order) -> SellOrderLine:
    """Seeds a single sell order line attached to the active_sell_order."""
    sell_order_line = SellOrderLine(
        id=uuid.uuid4(),
        sell_order_id=active_sell_order.id,
        item_id=None,
        quantity=5,
        unit_cost=250,
    )
    db_session.add(sell_order_line)
    db_session.commit()
    db_session.refresh(sell_order_line)
    return sell_order_line
