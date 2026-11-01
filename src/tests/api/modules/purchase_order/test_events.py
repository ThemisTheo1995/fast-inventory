import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.purchase_order.events import (
    PurchaseOrderCancelledEvent,
    PurchaseOrderLineAddedEvent,
    PurchaseOrderLineRemovedEvent,
    PurchaseOrderLineUpdatedEvent,
    PurchaseOrderReceivedEvent,
    PurchaseOrderReturnedEvent,
    PurchaseOrderSentEvent,
)
from erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine


@pytest.fixture
def db_session_mock():
    return MagicMock(spec=AsyncSession)


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
# Purchase Order Lifecycle Events
# ==============================================================================


@pytest.mark.parametrize(
    "event_class",
    [
        PurchaseOrderSentEvent,
        PurchaseOrderReceivedEvent,
        PurchaseOrderCancelledEvent,
        PurchaseOrderReturnedEvent,
    ],
)
def test_purchase_order_event_initialization(
    event_class,
    db_session_mock,
    workspace_id,
    purchase_order_mock,
):
    event = event_class(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock


# ==============================================================================
# Purchase Order Line Events
# ==============================================================================


def test_purchase_order_line_added_event_initialization(
    db_session_mock,
    workspace_id,
    purchase_order_mock,
    purchase_order_line_mock,
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


@pytest.mark.parametrize("quantity_delta", [-5, 0, 5])
def test_purchase_order_line_updated_event_initialization(
    db_session_mock,
    workspace_id,
    purchase_order_mock,
    purchase_order_line_mock,
    quantity_delta,
):
    event = PurchaseOrderLineUpdatedEvent(
        db=db_session_mock,
        workspace_id=workspace_id,
        purchase_order=purchase_order_mock,
        line=purchase_order_line_mock,
        quantity_delta=quantity_delta,
    )

    assert event.db is db_session_mock
    assert event.workspace_id == workspace_id
    assert event.purchase_order is purchase_order_mock
    assert event.line is purchase_order_line_mock
    assert event.quantity_delta == quantity_delta


def test_purchase_order_line_removed_event_initialization(
    db_session_mock,
    workspace_id,
    purchase_order_mock,
    purchase_order_line_mock,
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
