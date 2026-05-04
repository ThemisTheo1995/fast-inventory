from datetime import UTC, datetime, timedelta

from erp.integrations.ebay.items.adapter import EbayItemAdapter
from erp.integrations.ebay.items.repository import EbayItemRepository
from erp.integrations.ebay.items.schemas import EbayCreateItem, EbayItem


class EbayItemService:
    def __init__(self, adapter: EbayItemAdapter, repository: EbayItemRepository) -> None:
        self.adapter = adapter
        self.repository = repository

    def get_items(self) -> list[EbayItem]:
        return self.adapter.get_items(
            since=datetime.now(tz=UTC) - timedelta(days=30))

    def create_item(self, item_data: EbayCreateItem) -> EbayItem:
        """Create an eBay item explicitly in ERP's database (not on eBay)."""
        return self.repository.create(item_data)

    def sync_items(self) -> list[EbayItem]:
        return self.adapter.sync_items(
            since=datetime.now(tz=UTC) - timedelta(days=30))
