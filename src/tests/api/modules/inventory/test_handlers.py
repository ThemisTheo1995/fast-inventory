import uuid
from unittest.mock import ANY, MagicMock, patch

from src.erp.api.modules.inventory.enums import OrderType
from src.erp.api.modules.inventory.handlers import (
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
from src.erp.api.modules.inventory.schemas.stock_movement import StockMovementCreate
from src.erp.api.modules.purchase_order.events import (
    PurchaseOrderCancelledEvent,
    PurchaseOrderLineAddedEvent,
    PurchaseOrderLineRemovedEvent,
    PurchaseOrderLineUpdatedEvent,
    PurchaseOrderReceivedEvent,
    PurchaseOrderReturnedEvent,
    PurchaseOrderSentEvent,
)
from src.erp.api.modules.sell_order.events import (
    SellOrderCancelledEvent,
    SellOrderConfirmedEvent,
    SellOrderFulfilledEvent,
    SellOrderLineAddedEvent,
    SellOrderLineRemovedEvent,
    SellOrderLineUpdatedEvent,
    SellOrderReturnedEvent,
)
from src.erp.core.event_bus import EventBus
from src.tests.api.modules.inventory.conftest import create_mock_event, create_mock_line_event

# ==============================================================================
# PURCHASE ORDER HANDLER TESTS
# ==============================================================================


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_po_sent(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()
    event = create_mock_event(PurchaseOrderSentEvent, [(item_id, 10)])

    _handle_po_sent(event)

    mock_service.adjust_quantity_on_order.assert_called_once_with(event.workspace_id, item_id, 10)


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_po_received(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()
    event = create_mock_event(PurchaseOrderReceivedEvent, [(item_id, 5)])

    _handle_po_received(event)

    expected_movement = StockMovementCreate(
        item_id=item_id,
        quantity_change=5,
        reference_type=OrderType.PURCHASE_ORDER,
        reference_id=event.purchase_order.id,
    )

    mock_service.adjust_quantity_on_order.assert_called_once_with(event.workspace_id, item_id, -5)
    mock_service.create_stock_movement.assert_called_once_with(event.workspace_id, expected_movement)


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_po_cancelled(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()
    event = create_mock_event(PurchaseOrderCancelledEvent, [(item_id, 8)])

    _handle_po_cancelled(event)

    mock_service.adjust_quantity_on_order.assert_called_once_with(event.workspace_id, item_id, -8)


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_po_returned(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()
    event = create_mock_event(PurchaseOrderReturnedEvent, [(item_id, 3)])

    _handle_po_returned(event)

    expected_movement = StockMovementCreate(
        item_id=item_id,
        quantity_change=-3,
        reference_type=OrderType.PURCHASE_ORDER,
        reference_id=event.purchase_order.id,
    )

    mock_service.create_stock_movement.assert_called_once_with(event.workspace_id, expected_movement)


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_po_line_events(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()

    _handle_po_line_added(create_mock_line_event(PurchaseOrderLineAddedEvent, item_id, 4))
    mock_service.adjust_quantity_on_order.assert_called_with(ANY, item_id, 4)

    _handle_po_line_updated(create_mock_line_event(PurchaseOrderLineUpdatedEvent, item_id, 4, quantity_delta=2))
    mock_service.adjust_quantity_on_order.assert_called_with(ANY, item_id, 2)

    _handle_po_line_removed(create_mock_line_event(PurchaseOrderLineRemovedEvent, item_id, 4))
    mock_service.adjust_quantity_on_order.assert_called_with(ANY, item_id, -4)


# ==============================================================================
# SELL ORDER HANDLER TESTS
# ==============================================================================


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_so_confirmed(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()
    event = create_mock_event(SellOrderConfirmedEvent, [(item_id, 10)])

    _handle_so_confirmed(event)

    mock_service.adjust_quantity_allocated.assert_called_once_with(event.workspace_id, item_id, 10)


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_so_fulfilled(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()
    event = create_mock_event(SellOrderFulfilledEvent, [(item_id, 5)])

    _handle_so_fulfilled(event)

    expected_movement = StockMovementCreate(
        item_id=item_id,
        quantity_change=-5,
        reference_type=OrderType.SELL_ORDER,
        reference_id=event.sell_order.id,
    )

    mock_service.adjust_quantity_allocated.assert_called_once_with(event.workspace_id, item_id, -5)
    mock_service.create_stock_movement.assert_called_once_with(event.workspace_id, expected_movement)


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_so_cancelled(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()
    event = create_mock_event(SellOrderCancelledEvent, [(item_id, 8)])

    _handle_so_cancelled(event)

    mock_service.adjust_quantity_allocated.assert_called_once_with(event.workspace_id, item_id, -8)


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_so_returned(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()
    event = create_mock_event(SellOrderReturnedEvent, [(item_id, 3)])

    _handle_so_returned(event)

    expected_movement = StockMovementCreate(
        item_id=item_id,
        quantity_change=3,
        reference_type=OrderType.SELL_ORDER,
        reference_id=event.sell_order.id,
    )

    mock_service.create_stock_movement.assert_called_once_with(event.workspace_id, expected_movement)


@patch("src.erp.api.modules.inventory.handlers.InventoryService")
def test_handle_so_line_events(mock_inventory_service_class):
    mock_service = mock_inventory_service_class.return_value
    item_id = uuid.uuid4()

    _handle_so_line_added(create_mock_line_event(SellOrderLineAddedEvent, item_id, 4))
    mock_service.adjust_quantity_allocated.assert_called_with(ANY, item_id, 4)

    _handle_so_line_updated(create_mock_line_event(SellOrderLineUpdatedEvent, item_id, 4, quantity_delta=-1))
    mock_service.adjust_quantity_allocated.assert_called_with(ANY, item_id, -1)

    _handle_so_line_removed(create_mock_line_event(SellOrderLineRemovedEvent, item_id, 4))
    mock_service.adjust_quantity_allocated.assert_called_with(ANY, item_id, -4)


def test_register_inventory_handlers():
    """Verifies all handlers are correctly registered to the bus."""
    bus = MagicMock(spec=EventBus)
    register_inventory_handlers(bus)

    # Assert exactly 14 domain events are subscribed
    assert bus.subscribe.call_count == 14
