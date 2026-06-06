import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from erp.integrations.ebay.items.adapter import EbayItemAdapter
from erp.integrations.ebay.items.client import EbayItemClient
from erp.integrations.ebay.items.schemas import (
    EbayCreateItem,
    EbayItem,
    EbayPrice,
    EbayStatusEnum,
)

# ============================================================================
# FIXTURES & MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_client() -> MagicMock:
    """Provides a mocked EbayItemClient dependency layer."""
    return MagicMock(spec=EbayItemClient)


@pytest.fixture
def adapter(mock_client) -> EbayItemAdapter:
    """Instantiates the EbayItemAdapter with the mocked client injected."""
    return EbayItemAdapter(client=mock_client)


@pytest.fixture
def raw_ebay_item_dict() -> dict:
    """Provides a complete, standard mock dictionary payload from eBay."""
    return {
        "workspace_id": uuid.uuid4(),
        "sku": "SKU-WATCH-999",
        "availability": {"shipToLocationAvailability": {"quantity": 15}},
        "product": {
            "title": "Seiko Chronograph Pro",
            "imageUrls": ["https://example.com/watch.jpg"],
            "aspects": {"Brand": ["Seiko"], "Condition": ["New"]},
        },
        "price": {"value": "299.50", "currency": "GBP"},
        "listingId": "2948101001",
        "status": "ACTIVE",
    }


# ============================================================================
# ADAPTER LAYER ROUTINE METHOD TESTS
# ============================================================================


def test_sync_items_delegates_to_get_items(mock_client, adapter, raw_ebay_item_dict):
    """
    sync_items should delegate execution straight to get_items (per the
    current placeholder layout) and return valid mapped schemas.
    """
    now = datetime.now(tz=UTC)
    mock_client.get_items.return_value = [raw_ebay_item_dict]

    results = adapter.sync_items(since=now)

    assert len(results) == 1
    assert isinstance(results[0], EbayItem)
    assert results[0].sku == "SKU-WATCH-999"
    mock_client.get_items.assert_called_once_with(now)


def test_get_items_maps_multiple_raw_client_payloads(
    mock_client, adapter, raw_ebay_item_dict
):
    """
    get_items must capture raw dictionaries from the API client layer and
    safely project them into a collection of structured EbayItem data objects.
    """
    now = datetime.now(tz=UTC)
    # Duplicate payload to evaluate multi-row loop transformation tracking
    mock_client.get_items.return_value = [raw_ebay_item_dict, raw_ebay_item_dict]

    results = adapter.get_items(since=now)

    assert len(results) == 2
    assert all(isinstance(item, EbayItem) for item in results)
    mock_client.get_items.assert_called_once_with(now)


def test_create_item_raises_not_implemented(adapter):
    """
    create_item is not currently a supported adapter function and must
    explicitly raise a NotImplementedError when invoked.
    """
    mock_payload = MagicMock(spec=EbayCreateItem)

    with pytest.raises(NotImplementedError) as exc_info:
        adapter.create_item(mock_payload)

    assert str(exc_info.value) == "No implemented yet."


# ============================================================================
# DEEP MAPPING LOGIC & EDGE CASE TESTS (`_map_item`)
# ============================================================================


def test_map_item_happy_path_value_projection(adapter, raw_ebay_item_dict):
    """
    Verifies that nested values, type casting (floats), and deep keys extract
    and convert exactly to spec specifications.
    """
    result = adapter._map_item(raw_ebay_item_dict)

    assert isinstance(result, EbayItem)
    assert result.external_id == "2948101001"
    assert result.sku == "SKU-WATCH-999"
    assert result.name == "Seiko Chronograph Pro"
    assert result.stock_quantity == 15
    assert result.status == EbayStatusEnum.ACTIVE
    assert result.image_url == "https://example.com/watch.jpg"
    assert result.metadata == {"Brand": ["Seiko"], "Condition": ["New"]}

    # Deep price object validation
    assert isinstance(result.price, EbayPrice)
    assert result.price.value == 299.50
    assert result.price.currency == "GBP"


def test_map_item_edge_case_missing_listing_id_defaults(adapter, raw_ebay_item_dict):
    """
    If 'listingId' is completely absent from the incoming raw dictionary data,
    the mapping engine must fall back to 'N/A' to avoid key errors.
    """
    del raw_ebay_item_dict["listingId"]

    result = adapter._map_item(raw_ebay_item_dict)

    assert result.external_id == "N/A"


def test_map_item_edge_case_empty_or_missing_image_urls(adapter, raw_ebay_item_dict):
    """
    If the 'imageUrls' list field is missing or empty, the adapter should safely
    catch the list index and set the model's image_url field to None.
    """
    # Test path 1: Key exists but list array elements are completely empty
    raw_ebay_item_dict["product"]["imageUrls"] = []
    result_empty_list = adapter._map_item(raw_ebay_item_dict)
    assert result_empty_list.image_url is None

    # Test path 2: Key is missing entirely from product layout definitions
    del raw_ebay_item_dict["product"]["imageUrls"]
    result_missing_key = adapter._map_item(raw_ebay_item_dict)
    assert result_missing_key.image_url is None


def test_map_item_edge_case_missing_aspects_metadata(adapter, raw_ebay_item_dict):
    """
    If the product description does not contain an 'aspects' dictionary block,
    the metadata property must elegantly fall back to an empty dictionary structure.
    """
    del raw_ebay_item_dict["product"]["aspects"]

    result = adapter._map_item(raw_ebay_item_dict)

    assert result.metadata == {}
