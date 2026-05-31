from datetime import UTC, datetime, timedelta

from erp.api.modules.orders.schemas import MarketplaceOrder
from erp.integrations.ebay.orders.adapter import EbayOrderAdapter
from erp.integrations.ebay.orders.repository import EbayOrderRepository


class EbayOrderService:
    def __init__(self, adapter: EbayOrderAdapter, repository: EbayOrderRepository) -> None:
        self.adapter = adapter
        self.repository = repository

    def get_orders(self) -> list[MarketplaceOrder]:
        return self.adapter.get_orders(
            since=datetime.now(tz=UTC) - timedelta(days=30))

    def sync_orders(self) -> list[MarketplaceOrder]:
        return self.adapter.sync_orders(
            since=datetime.now(tz=UTC) - timedelta(days=30))
