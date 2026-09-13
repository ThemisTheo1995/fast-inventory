from src.erp.api.modules.sell_order.embeddings import (
    process_sell_order_search_index,
)
from src.erp.api.modules.sell_order.events import SellOrderCreatedEvent, SellOrderUpdatedEvent
from src.erp.core.event_bus import EventBus


async def _handle_sell_order_created(
    event: SellOrderCreatedEvent,
) -> None:
    await process_sell_order_search_index(event.sell_order.id)


async def _handle_sell_order_updated(
    event: SellOrderUpdatedEvent,
) -> None:
    await process_sell_order_search_index(event.sell_order.id)


def register_sell_order_handlers(bus: EventBus) -> None:
    """Subscribe sell_order embedding handlers to the event bus."""
    bus.subscribe(SellOrderCreatedEvent, _handle_sell_order_created)
    bus.subscribe(SellOrderUpdatedEvent, _handle_sell_order_updated)
