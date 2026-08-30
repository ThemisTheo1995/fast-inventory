# src/erp/api/modules/inventory/events.py
from src.erp.api.modules.inventory.enums import OrderType
from src.erp.api.modules.inventory.schemas.stock_movement import StockMovementCreate
from src.erp.api.modules.inventory.service import InventoryService
from src.erp.api.modules.purchase_order.events import (
    PurchaseOrderCancelledEvent,
    PurchaseOrderLineAddedEvent,
    PurchaseOrderLineRemovedEvent,
    PurchaseOrderLineUpdatedEvent,
    PurchaseOrderReceivedEvent,
    PurchaseOrderReturnedEvent,
    PurchaseOrderSentEvent,
)
from src.erp.core.event_bus import EventBus


def _handle_po_sent(event: PurchaseOrderSentEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            inventory_service.adjust_quantity_on_order(event.workspace_id, line.item_id, line.quantity)


def _handle_po_received(event: PurchaseOrderReceivedEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            inventory_service.adjust_quantity_on_order(event.workspace_id, line.item_id, -line.quantity)
            inventory_service.create_stock_movement(
                event.workspace_id,
                StockMovementCreate(
                    item_id=line.item_id,
                    quantity_change=line.quantity,
                    reference_type=OrderType.PURCHASE_ORDER,
                    reference_id=event.purchase_order.id,
                ),
            )


def _handle_po_cancelled(event: PurchaseOrderCancelledEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            inventory_service.adjust_quantity_on_order(event.workspace_id, line.item_id, -line.quantity)


def _handle_po_returned(event: PurchaseOrderReturnedEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            inventory_service.create_stock_movement(
                event.workspace_id,
                StockMovementCreate(
                    item_id=line.item_id,
                    quantity_change=-line.quantity,
                    reference_type=OrderType.PURCHASE_ORDER,
                    reference_id=event.purchase_order.id,
                ),
            )


def _handle_po_line_added(event: PurchaseOrderLineAddedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id:
        inventory_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, event.line.quantity)


def _handle_po_line_updated(event: PurchaseOrderLineUpdatedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id and event.quantity_delta != 0:
        inventory_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, event.quantity_delta)


def _handle_po_line_removed(event: PurchaseOrderLineRemovedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id:
        inventory_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, -event.line.quantity)


def register_inventory_handlers(bus: EventBus) -> None:
    """Subscribes inventory handlers to cross-module events."""
    # PO handlers
    bus.subscribe(PurchaseOrderSentEvent, _handle_po_sent)
    bus.subscribe(PurchaseOrderReceivedEvent, _handle_po_received)
    bus.subscribe(PurchaseOrderCancelledEvent, _handle_po_cancelled)
    bus.subscribe(PurchaseOrderReturnedEvent, _handle_po_returned)

    # PO line handlers
    bus.subscribe(PurchaseOrderLineAddedEvent, _handle_po_line_added)
    bus.subscribe(PurchaseOrderLineUpdatedEvent, _handle_po_line_updated)
    bus.subscribe(PurchaseOrderLineRemovedEvent, _handle_po_line_removed)
