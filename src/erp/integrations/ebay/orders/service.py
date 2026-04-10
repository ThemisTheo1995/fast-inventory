from datetime import UTC, datetime, timedelta

from erp.integrations.ebay.orders.adapter import EbayOrderAdapter
from erp.modules.orders.schemas import MarketplaceOrder


class EbayOrderService:
    def __init__(self, marketplace: EbayOrderAdapter) -> None:
        self.marketplace = marketplace

    def get_orders(self) -> list[MarketplaceOrder]:
        return self.marketplace.get_orders(
            since=datetime.now(tz=UTC) - timedelta(days=30))

    def sync_orders(self) -> list[MarketplaceOrder]:
        return self.marketplace.sync_orders(
            since=datetime.now(tz=UTC) - timedelta(days=30))
