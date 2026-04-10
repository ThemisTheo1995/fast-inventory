from datetime import UTC, datetime, timedelta

from erp.integrations.ebay.items.adapter import EbayItemAdapter
from erp.integrations.ebay.items.schemas import EbayItem


class EbayItemService:
    def __init__(self, marketplace: EbayItemAdapter) -> None:
        self.marketplace = marketplace

    def get_items(self) -> list[EbayItem]:
        return self.marketplace.get_items(
            since=datetime.now(tz=UTC) - timedelta(days=30))

    def sync_items(self) -> list[EbayItem]:
        return self.marketplace.sync_items(
            since=datetime.now(tz=UTC) - timedelta(days=30))
