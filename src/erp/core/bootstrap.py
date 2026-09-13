# src/erp/api/core/bootstrap.py
from src.erp.api.modules.customer.handlers import register_customer_handlers
from src.erp.api.modules.inventory.handlers import register_inventory_handlers
from src.erp.api.modules.purchase_order.handlers import register_purchase_order_handlers
from src.erp.api.modules.sell_order.handlers import register_sell_order_handlers
from src.erp.api.modules.supplier.handlers import register_supplier_handlers
from src.erp.core.event_bus import global_event_bus


def setup_application_events() -> None:
    """Registers all module-specific event handlers to the global bus."""
    register_customer_handlers(global_event_bus)

    register_inventory_handlers(global_event_bus)

    register_purchase_order_handlers(global_event_bus)

    register_sell_order_handlers(global_event_bus)

    register_supplier_handlers(global_event_bus)
