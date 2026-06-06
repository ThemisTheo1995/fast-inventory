from datetime import datetime
from typing import Protocol

from erp.api.modules.orders.schemas import MarketplaceCreateOrder, MarketplaceOrder


class MarketplaceOrderAdapter(Protocol):
    """Protocol all marketplace adapters must implement."""

    def get_orders(self, since: datetime) -> list[MarketplaceOrder]:
        """Fetch new orders from marketplace."""
        ...

    def create_order(self, order: MarketplaceCreateOrder) -> MarketplaceOrder:
        """Create an order on the marketplace."""
        ...

    def cancel_order(self, order_id: str) -> None:
        """Cancel an order."""
        ...

    def sync_orders(self) -> list[MarketplaceOrder]:
        """Explicit sync method (useful for FE button / cron)."""
        ...
