import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from erp.api.modules.inventory.handlers import (
    _handle_po_cancelled,
    _handle_po_line_added,
    _handle_po_line_removed,
    _handle_po_line_updated,
    _handle_po_received,
    _handle_po_returned,
    _handle_po_sent,
    _handle_so_cancelled,
    _handle_so_confirmed,
    _handle_so_fulfilled,
    _handle_so_line_added,
    _handle_so_line_removed,
    _handle_so_line_updated,
    _handle_so_returned,
    register_inventory_handlers,
)
from erp.api.modules.purchase_order.events import (
    PurchaseOrderCancelledEvent,
    PurchaseOrderLineAddedEvent,
    PurchaseOrderLineRemovedEvent,
    PurchaseOrderLineUpdatedEvent,
    PurchaseOrderReceivedEvent,
    PurchaseOrderReturnedEvent,
    PurchaseOrderSentEvent,
)
from erp.api.modules.sell_order.events import (
    SellOrderCancelledEvent,
    SellOrderConfirmedEvent,
    SellOrderFulfilledEvent,
    SellOrderLineAddedEvent,
    SellOrderLineRemovedEvent,
    SellOrderLineUpdatedEvent,
    SellOrderReturnedEvent,
)
from erp.core.event_bus import EventBus
from src.tests.api.modules.inventory.conftest import (
    create_mock_event,
    create_mock_line_event,
)

# ==============================================================================
# PURCHASE ORDER HANDLERS
# ==============================================================================


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_sent(mock_item_service_class):
    """Sending a PO increases the item's global quantity on order."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_event(PurchaseOrderSentEvent, [(item_id, 10)])

    await _handle_po_sent(event)

    mock_item_service_class.assert_called_once_with(event.db)
    mock_service.adjust_quantity_on_order.assert_awaited_once_with(event.workspace_id, item_id, 10)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_received(mock_item_service_class):
    """Receiving a PO reduces the item's global quantity on order."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_event(PurchaseOrderReceivedEvent, [(item_id, 5)])

    await _handle_po_received(event)

    mock_item_service_class.assert_called_once_with(event.db)
    mock_service.adjust_quantity_on_order.assert_awaited_once_with(event.workspace_id, item_id, -5)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_cancelled(mock_item_service_class):
    """Cancelling a PO removes its quantity from the global on-order total."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_event(PurchaseOrderCancelledEvent, [(item_id, 8)])

    await _handle_po_cancelled(event)

    mock_service.adjust_quantity_on_order.assert_awaited_once_with(event.workspace_id, item_id, -8)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_returned_is_noop(mock_item_service_class):
    """Returning a PO currently has no inventory or item quantity side effect."""
    item_id = uuid.uuid4()
    event = create_mock_event(PurchaseOrderReturnedEvent, [(item_id, 3)])

    await _handle_po_returned(event)

    mock_item_service_class.assert_not_called()


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_line_added(mock_item_service_class):
    """Adding a PO line increases quantity on order."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_line_event(PurchaseOrderLineAddedEvent, item_id, 4)

    await _handle_po_line_added(event)

    mock_service.adjust_quantity_on_order.assert_awaited_once_with(event.workspace_id, item_id, 4)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_line_updated(mock_item_service_class):
    """Updating a PO line applies only its quantity delta."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_line_event(
        PurchaseOrderLineUpdatedEvent,
        item_id,
        6,
        quantity_delta=2,
    )

    await _handle_po_line_updated(event)

    mock_service.adjust_quantity_on_order.assert_awaited_once_with(event.workspace_id, item_id, 2)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_line_updated_zero_delta(mock_item_service_class):
    """A zero quantity delta does not trigger an adjustment."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    event = create_mock_line_event(
        PurchaseOrderLineUpdatedEvent,
        uuid.uuid4(),
        6,
        quantity_delta=0,
    )

    await _handle_po_line_updated(event)

    mock_item_service_class.assert_called_once_with(event.db)
    mock_service.adjust_quantity_on_order.assert_not_awaited()


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_line_removed(mock_item_service_class):
    """Removing a PO line reduces quantity on order."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_line_event(PurchaseOrderLineRemovedEvent, item_id, 4)

    await _handle_po_line_removed(event)

    mock_service.adjust_quantity_on_order.assert_awaited_once_with(event.workspace_id, item_id, -4)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_po_handlers_ignore_lines_without_item(mock_item_service_class):
    """PO handlers skip service calls for lines without an item."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    event = create_mock_event(
        PurchaseOrderSentEvent,
        [(None, 10)],
    )

    await _handle_po_sent(event)

    mock_service.adjust_quantity_on_order.assert_not_awaited()


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_po_sent_multiple_lines(mock_item_service_class):
    """A PO with multiple item lines adjusts each item independently."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_on_order = AsyncMock()

    first_item_id = uuid.uuid4()
    second_item_id = uuid.uuid4()

    event = create_mock_event(
        PurchaseOrderSentEvent,
        [
            (first_item_id, 10),
            (second_item_id, 25),
        ],
    )

    await _handle_po_sent(event)

    assert mock_service.adjust_quantity_on_order.await_args_list == [
        call(event.workspace_id, first_item_id, 10),
        call(event.workspace_id, second_item_id, 25),
    ]


# ==============================================================================
# SALES ORDER HANDLERS
# ==============================================================================


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_confirmed(mock_item_service_class):
    """Confirming a SO increases the item's global allocated quantity."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_event(SellOrderConfirmedEvent, [(item_id, 10)])

    await _handle_so_confirmed(event)

    mock_item_service_class.assert_called_once_with(event.db)
    mock_service.adjust_quantity_allocated.assert_awaited_once_with(event.workspace_id, item_id, 10)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_fulfilled(mock_item_service_class):
    """Fulfilling a SO releases its allocated quantity."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_event(SellOrderFulfilledEvent, [(item_id, 5)])

    await _handle_so_fulfilled(event)

    mock_item_service_class.assert_called_once_with(event.db)
    mock_service.adjust_quantity_allocated.assert_awaited_once_with(event.workspace_id, item_id, -5)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_cancelled(mock_item_service_class):
    """Cancelling a SO releases its allocated quantity."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_event(SellOrderCancelledEvent, [(item_id, 8)])

    await _handle_so_cancelled(event)

    mock_service.adjust_quantity_allocated.assert_awaited_once_with(event.workspace_id, item_id, -8)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_returned_is_noop(mock_item_service_class):
    """Returning a SO currently has no item quantity side effect."""
    item_id = uuid.uuid4()
    event = create_mock_event(SellOrderReturnedEvent, [(item_id, 3)])

    await _handle_so_returned(event)

    mock_item_service_class.assert_not_called()


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_line_added(mock_item_service_class):
    """Adding a SO line increases allocated quantity."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_line_event(SellOrderLineAddedEvent, item_id, 4)

    await _handle_so_line_added(event)

    mock_service.adjust_quantity_allocated.assert_awaited_once_with(event.workspace_id, item_id, 4)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_line_updated(mock_item_service_class):
    """Updating a SO line applies only its quantity delta."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_line_event(
        SellOrderLineUpdatedEvent,
        item_id,
        4,
        quantity_delta=-1,
    )

    await _handle_so_line_updated(event)

    mock_service.adjust_quantity_allocated.assert_awaited_once_with(event.workspace_id, item_id, -1)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_line_updated_zero_delta(mock_item_service_class):
    """A zero quantity delta does not trigger an adjustment."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    event = create_mock_line_event(
        SellOrderLineUpdatedEvent,
        uuid.uuid4(),
        4,
        quantity_delta=0,
    )

    await _handle_so_line_updated(event)

    mock_item_service_class.assert_called_once_with(event.db)
    mock_service.adjust_quantity_allocated.assert_not_awaited()


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_line_removed(mock_item_service_class):
    """Removing a SO line releases its allocated quantity."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    item_id = uuid.uuid4()
    event = create_mock_line_event(SellOrderLineRemovedEvent, item_id, 4)

    await _handle_so_line_removed(event)

    mock_service.adjust_quantity_allocated.assert_awaited_once_with(event.workspace_id, item_id, -4)


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_so_handlers_ignore_lines_without_item(mock_item_service_class):
    """SO handlers skip service calls for lines without an item."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    event = create_mock_event(
        SellOrderConfirmedEvent,
        [(None, 10)],
    )

    await _handle_so_confirmed(event)

    mock_service.adjust_quantity_allocated.assert_not_awaited()


@pytest.mark.asyncio
@patch("erp.api.modules.inventory.handlers.ItemService")
async def test_handle_so_confirmed_multiple_lines(mock_item_service_class):
    """A SO with multiple item lines adjusts each item independently."""
    mock_service = mock_item_service_class.return_value
    mock_service.adjust_quantity_allocated = AsyncMock()

    first_item_id = uuid.uuid4()
    second_item_id = uuid.uuid4()

    event = create_mock_event(
        SellOrderConfirmedEvent,
        [
            (first_item_id, 10),
            (second_item_id, 25),
        ],
    )

    await _handle_so_confirmed(event)

    assert mock_service.adjust_quantity_allocated.await_args_list == [
        call(event.workspace_id, first_item_id, 10),
        call(event.workspace_id, second_item_id, 25),
    ]


# ==============================================================================
# EVENT REGISTRATION
# ==============================================================================


def test_register_inventory_handlers():
    """Verifies all 14 domain events are registered with their handlers."""
    bus = MagicMock(spec=EventBus)

    register_inventory_handlers(bus)

    expected_subscriptions = [
        call(PurchaseOrderSentEvent, _handle_po_sent),
        call(PurchaseOrderReceivedEvent, _handle_po_received),
        call(PurchaseOrderCancelledEvent, _handle_po_cancelled),
        call(PurchaseOrderReturnedEvent, _handle_po_returned),
        call(PurchaseOrderLineAddedEvent, _handle_po_line_added),
        call(PurchaseOrderLineUpdatedEvent, _handle_po_line_updated),
        call(PurchaseOrderLineRemovedEvent, _handle_po_line_removed),
        call(SellOrderConfirmedEvent, _handle_so_confirmed),
        call(SellOrderFulfilledEvent, _handle_so_fulfilled),
        call(SellOrderCancelledEvent, _handle_so_cancelled),
        call(SellOrderReturnedEvent, _handle_so_returned),
        call(SellOrderLineAddedEvent, _handle_so_line_added),
        call(SellOrderLineUpdatedEvent, _handle_so_line_updated),
        call(SellOrderLineRemovedEvent, _handle_so_line_removed),
    ]

    assert bus.subscribe.call_count == 14
    assert bus.subscribe.call_args_list == expected_subscriptions
