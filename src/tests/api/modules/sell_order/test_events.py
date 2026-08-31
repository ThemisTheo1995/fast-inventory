import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.erp.api.modules.sell_order.events import (
    SellOrderCancelledEvent,
    SellOrderConfirmedEvent,
    SellOrderFulfilledEvent,
    SellOrderLineAddedEvent,
    SellOrderLineRemovedEvent,
    SellOrderLineUpdatedEvent,
    SellOrderReturnedEvent,
)
from src.erp.api.modules.sell_order.models import SellOrder, SellOrderLine

# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def db_session_mock():
    return MagicMock(spec=Session)


@pytest.fixture
def workspace_id():
    return uuid.uuid4()


@pytest.fixture
def sell_order_mock():
    return MagicMock(spec=SellOrder)


@pytest.fixture
def sell_order_line_mock():
    return MagicMock(spec=SellOrderLine)


# ==============================================================================
# TESTS
# ==============================================================================


def test_sell_order_confirmed_event_initialization(db_session_mock, workspace_id, sell_order_mock):
    event = SellOrderConfirmedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        sell_order=sell_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.sell_order is sell_order_mock


def test_sell_order_fulfilled_event_initialization(db_session_mock, workspace_id, sell_order_mock):
    event = SellOrderFulfilledEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        sell_order=sell_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.sell_order is sell_order_mock


def test_sell_order_cancelled_event_initialization(db_session_mock, workspace_id, sell_order_mock):
    event = SellOrderCancelledEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        sell_order=sell_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.sell_order is sell_order_mock


def test_sell_order_returned_event_initialization(db_session_mock, workspace_id, sell_order_mock):
    event = SellOrderReturnedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        sell_order=sell_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.sell_order is sell_order_mock


def test_sell_order_line_added_event_initialization(
    db_session_mock, workspace_id, sell_order_mock, sell_order_line_mock
):
    event = SellOrderLineAddedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        sell_order=sell_order_mock,
        line=sell_order_line_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.sell_order is sell_order_mock
    assert event.line is sell_order_line_mock


def test_sell_order_line_updated_event_initialization(
    db_session_mock, workspace_id, sell_order_mock, sell_order_line_mock
):
    event = SellOrderLineUpdatedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        sell_order=sell_order_mock,
        line=sell_order_line_mock,
        quantity_delta=10,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.sell_order is sell_order_mock
    assert event.line is sell_order_line_mock
    assert event.quantity_delta == 10


def test_sell_order_line_removed_event_initialization(
    db_session_mock, workspace_id, sell_order_mock, sell_order_line_mock
):
    event = SellOrderLineRemovedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        sell_order=sell_order_mock,
        line=sell_order_line_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.sell_order is sell_order_mock
    assert event.line is sell_order_line_mock
