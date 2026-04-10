from datetime import UTC, datetime


class EbayOrderClient:
    """Client for interacting with eBay's Order API."""

    def get_orders(self, _since: datetime) -> list[dict]:
        return [
            {
                "orderId": "v1|1234567890|0",
                "creationDate": datetime.now(UTC).isoformat(),
                "pricingSummary": {
                    "total": {"value": "59.98", "currency": "GBP"}
                },
                "lineItems": [
                    {
                        "sku": "TSHIRT-BLACK-M",
                        "quantity": 2,
                        "lineItemCost": {"value": "19.99"},
                    },
                    {
                        "sku": "CAP-RED",
                        "quantity": 1,
                        "lineItemCost": {"value": "19.99"},
                    },
                ],
            }
        ]

    def create_order(self, _order_data: dict) -> dict:
        raise NotImplementedError("eBay doesn't support direct order creation")

    def cancel_order(self, order_id: str) -> None:
        print(f"[MOCK EBAY] Cancel order {order_id}")
