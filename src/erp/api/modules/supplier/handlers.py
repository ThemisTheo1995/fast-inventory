from src.erp.api.modules.supplier.embeddings import (
    process_supplier_search_index,
)
from src.erp.api.modules.supplier.events import (
    SupplierCreatedEvent,
    SupplierUpdatedEvent,
)
from src.erp.core.event_bus import EventBus


async def _handle_supplier_created(
    event: SupplierCreatedEvent,
) -> None:
    await process_supplier_search_index(event.supplier.id)


async def _handle_supplier_updated(
    event: SupplierUpdatedEvent,
) -> None:
    await process_supplier_search_index(event.supplier.id)


def register_supplier_handlers(bus: EventBus) -> None:
    """Subscribe supplier embedding handlers to the event bus."""
    bus.subscribe(SupplierCreatedEvent, _handle_supplier_created)
    bus.subscribe(SupplierUpdatedEvent, _handle_supplier_updated)
