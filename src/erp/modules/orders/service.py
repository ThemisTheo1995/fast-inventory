from datetime import UTC, datetime

from src.erp.modules.orders.adapter import StandardOrderAdapter
from src.erp.modules.orders.schemas import MarketplaceCreateOrder, MarketplaceOrder


class OrderService:
    def __init__(self, marketplace: StandardOrderAdapter) -> None:
        self.marketplace = marketplace

    def list_orders(self) -> list[MarketplaceOrder]:
        orders = self.marketplace.get_orders(since=datetime(2024, 1, 1, tzinfo=UTC))
        for order in orders:
            self._save_to_erp(order)
        return orders

    def create_order(self, order_data: MarketplaceCreateOrder) -> MarketplaceOrder:
        new_order = self.marketplace.create_order(order_data)
        self._save_to_erp(new_order)
        return new_order

    def _save_to_erp(self, order: MarketplaceOrder) -> None:
        print(f"DEBUG: Saving {order.external_id} to ERP Database...")
