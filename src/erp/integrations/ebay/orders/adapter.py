from datetime import datetime
from decimal import Decimal

from erp.integrations.ebay.orders.client import EbayOrderClient
from erp.modules.orders.adapter import MarketplaceOrderAdapter
from erp.modules.orders.schemas import (
    MarketplaceOrder,
    MarketplaceOrderItem,
)


class EbayOrderAdapter(MarketplaceOrderAdapter):
    def __init__(self, client: EbayOrderClient) -> None:
        self.client = client

    def sync_orders(self, since: datetime) -> list[MarketplaceOrder]:
        return self.get_orders(since=since)     # TODO: Replace with actual sync logic

    def get_orders(self, since: datetime) -> list[MarketplaceOrder]:
        raw_orders = self.client.get_orders(since)
        return [self._map_order(o) for o in raw_orders]

    def create_order(self, _order: None) -> None:
        raise NotImplementedError("eBay is read-only for orders")

    def cancel_order(self, order_id: str) -> None:
        self.client.cancel_order(order_id)

    def _map_order(self, raw: dict) -> MarketplaceOrder:
        return MarketplaceOrder(
            external_id=raw["orderId"],
            marketplace="ebay",
            total=Decimal(raw["pricingSummary"]["total"]["value"]),
            currency=raw["pricingSummary"]["total"]["currency"],
            created_at=datetime.fromisoformat(raw["creationDate"]),
            items=[
                MarketplaceOrderItem(
                    sku=item["sku"],
                    quantity=item["quantity"],
                    price=Decimal(item["lineItemCost"]["value"]),
                )
                for item in raw.get("lineItems", [])
            ],
        )
