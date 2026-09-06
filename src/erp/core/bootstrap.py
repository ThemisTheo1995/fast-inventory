# src/erp/api/core/bootstrap.py
from erp.api.modules.customer.handlers import register_customer_handlers
from erp.api.modules.inventory.handlers import register_inventory_handlers
from erp.core.event_bus import global_event_bus


def setup_application_events() -> None:
    """Registers all module-specific event handlers to the global bus."""
    register_inventory_handlers(global_event_bus)
    register_customer_handlers(global_event_bus)
