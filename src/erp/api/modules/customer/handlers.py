from src.erp.api.modules.customer.embeddings import (
    process_customer_search_index,
)
from src.erp.api.modules.customer.events import (
    CustomerCreatedEvent,
    CustomerUpdatedEvent,
)
from src.erp.core.event_bus import EventBus


async def _handle_customer_created(
    event: CustomerCreatedEvent,
) -> None:
    await process_customer_search_index(event.customer.id)


async def _handle_customer_updated(
    event: CustomerUpdatedEvent,
) -> None:
    await process_customer_search_index(event.customer.id)


def register_customer_handlers(bus: EventBus) -> None:
    """Subscribe customer embedding handlers to the event bus."""
    bus.subscribe(CustomerCreatedEvent, _handle_customer_created)
    bus.subscribe(CustomerUpdatedEvent, _handle_customer_updated)
