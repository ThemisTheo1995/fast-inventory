from erp.api.modules.bin.embeddings import process_bin_search_index
from erp.api.modules.bin.events import (
    BinCreatedEvent,
    BinUpdatedEvent,
)
from erp.core.event_bus import EventBus


async def _handle_bin_created(event: BinCreatedEvent) -> None:
    await process_bin_search_index(event.bin.id)


async def _handle_bin_updated(event: BinUpdatedEvent) -> None:
    await process_bin_search_index(event.bin.id)


def register_bin_handlers(bus: EventBus) -> None:
    """Subscribe bin embedding handlers to the event bus."""
    bus.subscribe(BinCreatedEvent, _handle_bin_created)
    bus.subscribe(BinUpdatedEvent, _handle_bin_updated)
