from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from erp.integrations.ebay.items.schemas import EbayCreateItem
from erp.integrations.ebay.items.service import EbayItemService

# ============================================================================
# FIXTURES & CORE DEPENDENCY SETUPS
# ============================================================================


@pytest.fixture
def mock_adapter() -> MagicMock:
    """Provides a mocked engine representing the external eBay API adapter."""
    return MagicMock()


@pytest.fixture
def mock_repository() -> MagicMock:
    """Provides a mocked database repository layer for EbayItem elements."""
    return MagicMock()


@pytest.fixture
def target_service(mock_adapter, mock_repository) -> EbayItemService:
    """Instantiates the orchestration service injecting mock engine modules."""
    return EbayItemService(adapter=mock_adapter, repository=mock_repository)


# ============================================================================
# EBAY ITEM SERVICE LAYER TESTS
# ============================================================================


def test_get_items_calculates_correct_30_day_delta(mock_adapter, target_service):
    """
    HAPPY PATH:
    Executing get_items should calculate a historical time floor exactly 30 days
    prior to execution time and forward it down to the adapter layer cleanly.
    """
    fixed_now = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    expected_since = fixed_now - timedelta(days=30)

    mock_items_list = [MagicMock(name="MockEbayItem")]
    mock_adapter.get_items.return_value = mock_items_list

    with patch("erp.integrations.ebay.items.service.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        result = target_service.get_items()

    assert result == mock_items_list
    mock_adapter.get_items.assert_called_once_with(since=expected_since)


def test_create_item_delegates_explicitly_to_repository(
    mock_repository, target_service
):
    """
    Creating an item must hand off the exact schema payload to the database
    repository without intercepting or mutating its properties.
    """
    payload = MagicMock(spec=EbayCreateItem)
    mock_saved_item = MagicMock(name="MockEbayItem")
    mock_repository.create.return_value = mock_saved_item

    result = target_service.create_item(payload)

    assert result == mock_saved_item
    mock_repository.create.assert_called_once_with(payload)


def test_sync_items_calculates_correct_30_day_delta(mock_adapter, target_service):
    """
    Sync loops must correctly calculate the 30-day lookback floor and delegate
    the sync payload retrieval tasks over to the adapter pipeline safely.
    """
    fixed_now = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    expected_since = fixed_now - timedelta(days=30)

    mock_synced_items = [MagicMock(name="MockSyncedEbayItem")]
    mock_adapter.sync_items.return_value = mock_synced_items

    with patch("erp.integrations.ebay.items.service.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        result = target_service.sync_items()

    assert result == mock_synced_items
    mock_adapter.sync_items.assert_called_once_with(since=expected_since)
