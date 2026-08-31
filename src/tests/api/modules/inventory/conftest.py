import uuid
from unittest.mock import MagicMock

import pytest

from src.erp.api.modules.inventory.models import Inventory
from src.erp.api.modules.item.models import Item

# ==============================================================================
# FIXTURES & HELPERS
# ==============================================================================


def create_mock_event(event_class, lines_data):
    """Helper to create a mock event with nested lines."""
    event = MagicMock(spec=event_class)
    event.workspace_id = uuid.uuid4()
    event.db = MagicMock()

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
    event.db = MagicMock()

    line = MagicMock()
    line.item_id = item_id
    line.quantity = quantity
    event.line = line

    if quantity_delta is not None:
        event.quantity_delta = quantity_delta

    return event


@pytest.fixture
def active_item(db_session, seed_workspace) -> Item:
    """Seeds a live item record (with automatic inventory initialization) for inventory testing."""
    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        title="Inventory Test Item",
        sku="INV-TEST-001",
        base_price=1500,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    inventory = Inventory(
        workspace_id=seed_workspace,
        item_id=item.id,
        quantity_on_hand=0,
        quantity_allocated=0,
        quantity_on_order=0,
    )
    db_session.add(inventory)
    db_session.commit()

    return item


@pytest.fixture
def empty_item(db_session, seed_workspace) -> Item:
    """Creates an item but does NOT initialize its inventory."""
    item = Item(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        title="Empty Item",
        sku=f"EMPTY-{uuid.uuid4().hex[:6]}",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item
