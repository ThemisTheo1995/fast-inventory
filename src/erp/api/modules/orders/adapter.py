from datetime import UTC, datetime
from typing import Protocol

from erp.api.modules.orders.client import StandardClient
from erp.api.modules.orders.schemas import (
    MarketplaceCreateOrder,
    MarketplaceOrder,
    MarketplaceOrderItem,
)


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


class StandardOrderAdapter(MarketplaceOrderAdapter):
    def __init__(self, client: StandardClient) -> None:
        self.client = client

    def get_orders(self, since: datetime) -> list[MarketplaceOrder]:
        raw_orders = self.client.get_orders(since)
        return [self._map_raw_order(o) for o in raw_orders]

    def create_order(self, order: MarketplaceCreateOrder) -> MarketplaceOrder:
        raw_order = self.client.create_order(order.model_dump())
        return self._map_raw_order(raw_order)

    def cancel_order(self, order_id: str) -> None:
        self.client.cancel_order(order_id)

    def _map_raw_order(self, raw_order: dict) -> MarketplaceOrder:
        return MarketplaceOrder(
            external_id=raw_order.get("external_id", "N/A"),
            marketplace=raw_order.get("marketplace", "standard"),
            total=raw_order.get("total", 0.0),
            currency=raw_order.get("currency", "USD"),
            created_at=raw_order.get("created_at") or datetime.now(UTC),
            items=[
                MarketplaceOrderItem(**item) for item in raw_order.get("items", [])
            ]
        )
