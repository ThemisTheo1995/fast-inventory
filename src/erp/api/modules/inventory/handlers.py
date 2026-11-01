from erp.api.modules.item.service import ItemService
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

# ==============================================================================
# PURCHASE ORDER HANDLERS
# ==============================================================================


async def _handle_po_sent(event: PurchaseOrderSentEvent) -> None:
    item_service = ItemService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            await item_service.adjust_quantity_on_order(event.workspace_id, line.item_id, line.quantity)


async def _handle_po_received(event: PurchaseOrderReceivedEvent) -> None:
    item_service = ItemService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            await item_service.adjust_quantity_on_order(event.workspace_id, line.item_id, -line.quantity)


async def _handle_po_cancelled(event: PurchaseOrderCancelledEvent) -> None:
    item_service = ItemService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            await item_service.adjust_quantity_on_order(event.workspace_id, line.item_id, -line.quantity)


async def _handle_po_returned(event: PurchaseOrderReturnedEvent) -> None:
    pass


async def _handle_po_line_added(event: PurchaseOrderLineAddedEvent) -> None:
    item_service = ItemService(event.db)
    if event.line.item_id:
        await item_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, event.line.quantity)


async def _handle_po_line_updated(event: PurchaseOrderLineUpdatedEvent) -> None:
    item_service = ItemService(event.db)
    if event.line.item_id and event.quantity_delta != 0:
        await item_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, event.quantity_delta)


async def _handle_po_line_removed(event: PurchaseOrderLineRemovedEvent) -> None:
    item_service = ItemService(event.db)
    if event.line.item_id:
        await item_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, -event.line.quantity)


# ==============================================================================
# SELL ORDER HANDLERS
# ==============================================================================


async def _handle_so_confirmed(event: SellOrderConfirmedEvent) -> None:
    item_service = ItemService(event.db)
    for line in event.sell_order.sell_order_lines:
        if line.item_id:
            await item_service.adjust_quantity_allocated(event.workspace_id, line.item_id, line.quantity)


async def _handle_so_fulfilled(event: SellOrderFulfilledEvent) -> None:
    item_service = ItemService(event.db)
    for line in event.sell_order.sell_order_lines:
        if line.item_id:
            await item_service.adjust_quantity_allocated(event.workspace_id, line.item_id, -line.quantity)


async def _handle_so_cancelled(event: SellOrderCancelledEvent) -> None:
    item_service = ItemService(event.db)
    for line in event.sell_order.sell_order_lines:
        if line.item_id:
            await item_service.adjust_quantity_allocated(event.workspace_id, line.item_id, -line.quantity)


async def _handle_so_returned(event: SellOrderReturnedEvent) -> None:
    pass


async def _handle_so_line_added(event: SellOrderLineAddedEvent) -> None:
    item_service = ItemService(event.db)
    if event.line.item_id:
        await item_service.adjust_quantity_allocated(event.workspace_id, event.line.item_id, event.line.quantity)


async def _handle_so_line_updated(event: SellOrderLineUpdatedEvent) -> None:
    item_service = ItemService(event.db)
    if event.line.item_id and event.quantity_delta != 0:
        await item_service.adjust_quantity_allocated(event.workspace_id, event.line.item_id, event.quantity_delta)


async def _handle_so_line_removed(event: SellOrderLineRemovedEvent) -> None:
    item_service = ItemService(event.db)
    if event.line.item_id:
        await item_service.adjust_quantity_allocated(event.workspace_id, event.line.item_id, -event.line.quantity)


# ==============================================================================
# REGISTRATION
# ==============================================================================


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

    # SO handlers
    bus.subscribe(SellOrderConfirmedEvent, _handle_so_confirmed)
    bus.subscribe(SellOrderFulfilledEvent, _handle_so_fulfilled)
    bus.subscribe(SellOrderCancelledEvent, _handle_so_cancelled)
    bus.subscribe(SellOrderReturnedEvent, _handle_so_returned)

    # SO line handlers
    bus.subscribe(SellOrderLineAddedEvent, _handle_so_line_added)
    bus.subscribe(SellOrderLineUpdatedEvent, _handle_so_line_updated)
    bus.subscribe(SellOrderLineRemovedEvent, _handle_so_line_removed)
