import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.erp.api.modules.purchase_order.events import (
    PurchaseOrderCancelledEvent,
    PurchaseOrderLineAddedEvent,
    PurchaseOrderLineRemovedEvent,
    PurchaseOrderLineUpdatedEvent,
    PurchaseOrderReceivedEvent,
    PurchaseOrderReturnedEvent,
    PurchaseOrderSentEvent,
)
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine

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
def purchase_order_mock():
    return MagicMock(spec=PurchaseOrder)


@pytest.fixture
def purchase_order_line_mock():
    return MagicMock(spec=PurchaseOrderLine)


# ==============================================================================
# TESTS
# ==============================================================================


def test_purchase_order_sent_event_initialization(db_session_mock, workspace_id, purchase_order_mock):
    event = PurchaseOrderSentEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock


def test_purchase_order_received_event_initialization(db_session_mock, workspace_id, purchase_order_mock):
    event = PurchaseOrderReceivedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock


def test_purchase_order_cancelled_event_initialization(db_session_mock, workspace_id, purchase_order_mock):
    event = PurchaseOrderCancelledEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock


def test_purchase_order_returned_event_initialization(db_session_mock, workspace_id, purchase_order_mock):
    event = PurchaseOrderReturnedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock


def test_purchase_order_line_added_event_initialization(
    db_session_mock, workspace_id, purchase_order_mock, purchase_order_line_mock
):
    event = PurchaseOrderLineAddedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
        line=purchase_order_line_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock
    assert event.line is purchase_order_line_mock


def test_purchase_order_line_updated_event_initialization(
    db_session_mock, workspace_id, purchase_order_mock, purchase_order_line_mock
):
    event = PurchaseOrderLineUpdatedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
        line=purchase_order_line_mock,
        quantity_delta=-5,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock
    assert event.line is purchase_order_line_mock
    assert event.quantity_delta == -5


def test_purchase_order_line_removed_event_initialization(
    db_session_mock, workspace_id, purchase_order_mock, purchase_order_line_mock
):
    event = PurchaseOrderLineRemovedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
        line=purchase_order_line_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock
    assert event.line is purchase_order_line_mock
