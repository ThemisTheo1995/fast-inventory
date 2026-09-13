from src.erp.api.modules.purchase_order.embeddings import (
    process_purchase_order_search_index,
)
from src.erp.api.modules.purchase_order.events import PurchaseOrderCreatedEvent, PurchaseOrderUpdatedEvent
from src.erp.core.event_bus import EventBus


async def _handle_purchase_order_created(
    event: PurchaseOrderCreatedEvent,
) -> None:
    await process_purchase_order_search_index(event.purchase_order.id)


async def _handle_purchase_order_updated(
    event: PurchaseOrderUpdatedEvent,
) -> None:
    await process_purchase_order_search_index(event.purchase_order.id)


def register_purchase_order_handlers(bus: EventBus) -> None:
    """Subscribe purchase_order embedding handlers to the event bus."""
    bus.subscribe(PurchaseOrderCreatedEvent, _handle_purchase_order_created)
    bus.subscribe(PurchaseOrderUpdatedEvent, _handle_purchase_order_updated)
