from datetime import datetime
from typing import Protocol

from erp.api.modules.items.schemas import (
    MarketplaceCreateItem,
    MarketplaceItem,
)


class MarketplaceItemAdapter(Protocol):
    """Protocol all marketplace adapters must implement."""

    def get_items(self, since: datetime) -> list[MarketplaceItem]:
        """Fetch new items from marketplace."""
        ...

    def create_item(self, item: MarketplaceCreateItem) -> MarketplaceItem:
        """Create an item on the marketplace."""
        ...

    def delete_item(self, item_id: str) -> None:
        """Delete an item from the marketplace."""
        ...

    def sync_items(self) -> list[MarketplaceItem]:
        """Explicit sync method (useful for FE button / cron)."""
        ...
