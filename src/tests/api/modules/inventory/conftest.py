import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio

from erp.api.modules.bin.models import Bin
from erp.api.modules.inventory.models import Inventory
from erp.api.modules.item.models import Item

# ==============================================================================
# FIXTURES & HELPERS
# ==============================================================================


def create_mock_event(event_class, lines_data):
    """Helper to create a mock event with nested lines."""
    event = MagicMock(spec=event_class)
    event.workspace_id = uuid.uuid4()
    event.db = AsyncMock()

    order_mock = MagicMock()
    order_mock.id = uuid.uuid4()

    lines = []

    for item_id, quantity in lines_data:
        line = MagicMock()
        line.item_id = item_id
        line.quantity = quantity
        lines.append(line)

    if "PurchaseOrder" in event_class.__name__:
        order_mock.purchase_order_lines = lines
        event.purchase_order = order_mock
    else:
        order_mock.sell_order_lines = lines
        event.sell_order = order_mock

    return event


def create_mock_line_event(event_class, item_id, quantity, quantity_delta=None):
    """Helper to create line-level events."""
    event = MagicMock(spec=event_class)
    event.workspace_id = uuid.uuid4()
    event.db = AsyncMock()

    line = MagicMock()
    line.item_id = item_id
    line.quantity = quantity
    event.line = line

    if quantity_delta is not None:
        event.quantity_delta = quantity_delta

    return event


# ==============================================================================
# DATABASE FIXTURES
# ==============================================================================


@pytest_asyncio.fixture
async def seed_bin(db_session, seed_workspace) -> Bin:
    """Creates an active bin for inventory tests."""
    bin = Bin(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        code=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        zone="Test Warehouse",
        is_deleted=False,
    )

    db_session.add(bin)
    await db_session.commit()
    await db_session.refresh(bin)

    return bin


@pytest_asyncio.fixture
async def active_item(db_session, seed_workspace, seed_bin) -> Item:
    """Creates an active item with zero-quantity inventory in a real bin."""
    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        title="Inventory Test Item",
        sku=f"INV-{uuid.uuid4().hex[:8].upper()}",
        base_price=1500,
        is_deleted=False,
    )

    db_session.add(item)
    await db_session.flush()

    inventory = Inventory(
        workspace_id=seed_workspace,
        item_id=item.id,
        bin_id=seed_bin.id,
        quantity_on_hand=0,
    )

    db_session.add(inventory)
    await db_session.commit()
    await db_session.refresh(item)

    return item


@pytest_asyncio.fixture
async def empty_item(db_session, seed_workspace) -> Item:
    """Creates an active item without initializing its inventory."""
    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        title="Empty Item",
        sku=f"EMPTY-{uuid.uuid4().hex[:8].upper()}",
        base_price=100,
        is_deleted=False,
    )

    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    return item
