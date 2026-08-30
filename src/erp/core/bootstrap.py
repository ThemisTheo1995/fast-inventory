# src/erp/api/core/bootstrap.py
from src.erp.api.modules.inventory.handlers import register_inventory_handlers
from src.erp.core.event_bus import global_event_bus


def setup_application_events() -> None:
    """Registers all module-specific event handlers to the global bus."""
    register_inventory_handlers(global_event_bus)
