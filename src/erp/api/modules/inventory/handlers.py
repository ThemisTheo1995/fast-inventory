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

# ==============================================================================
# PURCHASE ORDER HANDLERS
# ==============================================================================


async def _handle_po_sent(event: PurchaseOrderSentEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            await inventory_service.adjust_quantity_on_order(event.workspace_id, line.item_id, line.quantity)


async def _handle_po_received(event: PurchaseOrderReceivedEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            await inventory_service.adjust_quantity_on_order(event.workspace_id, line.item_id, -line.quantity)
            await inventory_service.create_stock_movement(
                event.workspace_id,
                StockMovementCreate(
                    item_id=line.item_id,
                    quantity_change=line.quantity,
                    reference_type=OrderType.PURCHASE_ORDER,
                    reference_id=event.purchase_order.id,
                ),
            )


async def _handle_po_cancelled(event: PurchaseOrderCancelledEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            await inventory_service.adjust_quantity_on_order(event.workspace_id, line.item_id, -line.quantity)


async def _handle_po_returned(event: PurchaseOrderReturnedEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.purchase_order.purchase_order_lines:
        if line.item_id:
            await inventory_service.create_stock_movement(
                event.workspace_id,
                StockMovementCreate(
                    item_id=line.item_id,
                    quantity_change=-line.quantity,
                    reference_type=OrderType.PURCHASE_ORDER,
                    reference_id=event.purchase_order.id,
                ),
            )


async def _handle_po_line_added(event: PurchaseOrderLineAddedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id:
        await inventory_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, event.line.quantity)


async def _handle_po_line_updated(event: PurchaseOrderLineUpdatedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id and event.quantity_delta != 0:
        await inventory_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, event.quantity_delta)


async def _handle_po_line_removed(event: PurchaseOrderLineRemovedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id:
        await inventory_service.adjust_quantity_on_order(event.workspace_id, event.line.item_id, -event.line.quantity)


# ==============================================================================
# SELL ORDER HANDLERS
# ==============================================================================


async def _handle_so_confirmed(event: SellOrderConfirmedEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.sell_order.sell_order_lines:
        if line.item_id:
            await inventory_service.adjust_quantity_allocated(event.workspace_id, line.item_id, line.quantity)


async def _handle_so_fulfilled(event: SellOrderFulfilledEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.sell_order.sell_order_lines:
        if line.item_id:
            await inventory_service.adjust_quantity_allocated(event.workspace_id, line.item_id, -line.quantity)
            await inventory_service.create_stock_movement(
                event.workspace_id,
                StockMovementCreate(
                    item_id=line.item_id,
                    quantity_change=-line.quantity,
                    reference_type=OrderType.SELL_ORDER,
                    reference_id=event.sell_order.id,
                ),
            )


async def _handle_so_cancelled(event: SellOrderCancelledEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.sell_order.sell_order_lines:
        if line.item_id:
            await inventory_service.adjust_quantity_allocated(event.workspace_id, line.item_id, -line.quantity)


async def _handle_so_returned(event: SellOrderReturnedEvent) -> None:
    inventory_service = InventoryService(event.db)
    for line in event.sell_order.sell_order_lines:
        if line.item_id:
            await inventory_service.create_stock_movement(
                event.workspace_id,
                StockMovementCreate(
                    item_id=line.item_id,
                    quantity_change=line.quantity,
                    reference_type=OrderType.SELL_ORDER,
                    reference_id=event.sell_order.id,
                ),
            )


async def _handle_so_line_added(event: SellOrderLineAddedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id:
        await inventory_service.adjust_quantity_allocated(event.workspace_id, event.line.item_id, event.line.quantity)


async def _handle_so_line_updated(event: SellOrderLineUpdatedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id and event.quantity_delta != 0:
        await inventory_service.adjust_quantity_allocated(event.workspace_id, event.line.item_id, event.quantity_delta)


async def _handle_so_line_removed(event: SellOrderLineRemovedEvent) -> None:
    inventory_service = InventoryService(event.db)
    if event.line.item_id:
        await inventory_service.adjust_quantity_allocated(event.workspace_id, event.line.item_id, -event.line.quantity)


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
