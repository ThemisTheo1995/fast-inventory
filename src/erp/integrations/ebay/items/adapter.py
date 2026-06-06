from datetime import datetime

from erp.api.modules.items.adapter import MarketplaceItemAdapter
from erp.integrations.ebay.items.client import EbayItemClient
from erp.integrations.ebay.items.schemas import (
    EbayCreateItem,
    EbayItem,
    EbayPrice,
    EbayStatusEnum,
)


class EbayItemAdapter(MarketplaceItemAdapter):
    def __init__(self, client: EbayItemClient) -> None:
        self.client = client

    def sync_items(self, since: datetime) -> list[EbayItem]:
        return self.get_items(since=since)     # TODO: Replace with actual sync logic

    def get_items(self, since: datetime) -> list[EbayItem]:
        raw_items = self.client.get_items(since)
        return [self._map_item(o) for o in raw_items]

    def create_item(self, _create_item: EbayCreateItem) -> EbayItem:
        raise NotImplementedError("No implemented yet.")

    def delete_item(self, order_id: str) -> None:
        self.client.cancel_order(order_id)

    def _map_item(self, raw: dict) -> EbayItem:
        image_urls = raw["product"].get("imageUrls")
        image_url = image_urls[0] if image_urls else None

        return EbayItem(
            workspace_id=raw.get("workspace_id"),
            external_id=raw.get("listingId", "N/A"),
            sku=raw["sku"],
            name=raw["product"]["title"],
            price=EbayPrice(
                value=float(raw["price"]["value"]),
                currency=raw["price"]["currency"],
            ),
            stock_quantity=raw["availability"]["shipToLocationAvailability"][
                "quantity"
            ],
            status=EbayStatusEnum(raw["status"]),
            image_url=image_url,
            metadata=raw["product"].get("aspects", {}),
        )
