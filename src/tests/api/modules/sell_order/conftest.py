import uuid

import pytest

from erp.api.modules.customer.models import Customer
from erp.api.modules.inventory.enums import OrderType
from erp.api.modules.inventory.schemas.stock_movement import StockMovementCreate
from erp.api.modules.inventory.service import InventoryService
from erp.api.modules.item.models import Item
from erp.api.modules.sell_order.enums import SOStatusEnum
from erp.api.modules.sell_order.models import SellOrder, SellOrderLine

# --- CUSTOMER FIXTURES ---


@pytest.fixture
async def active_customer(db_session, seed_workspace) -> Customer:
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
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


# --- ITEM & INVENTORY FIXTURES ---


@pytest.fixture
async def active_item(db_session, seed_workspace) -> Item:
    """Seeds a base item without stock."""
    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        title="Fixture Test Item",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


@pytest.fixture
async def stocked_item(db_session, seed_workspace, active_item) -> Item:
    """Seeds physical stock (100 units) so allocation checks pass in tests."""
    inv_service = InventoryService(db_session)
    await inv_service.create_stock_movement(
        seed_workspace,
        StockMovementCreate(
            item_id=active_item.id,
            quantity_change=100,
            reference_type=OrderType.PURCHASE_ORDER,
            reference_id=uuid.uuid4(),
        ),
    )
    await db_session.flush()
    return active_item


# --- SELL ORDER FIXTURES ---


@pytest.fixture
async def active_sell_order(db_session, seed_workspace, active_customer) -> SellOrder:
    """Seeds a live sell order record attached to the primary workspace and active customer."""
    sell_order = SellOrder(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        customer_id=active_customer.id,
        so_number="SO-FIXTURE-001",
        total_amount=1250,
        status=SOStatusEnum.DRAFT,
    )
    db_session.add(sell_order)
    await db_session.commit()
    await db_session.refresh(sell_order)
    return sell_order


@pytest.fixture
async def active_sell_order_line(db_session, active_sell_order, stocked_item) -> SellOrderLine:
    """Seeds a single sell order line attached to an active_sell_order and linked to a stocked_item."""
    sell_order_line = SellOrderLine(
        id=uuid.uuid4(),
        sell_order_id=active_sell_order.id,
        item_id=stocked_item.id,
        quantity=5,
        unit_cost=250,
    )
    db_session.add(sell_order_line)
    await db_session.commit()
    await db_session.refresh(sell_order_line)
    return sell_order_line
