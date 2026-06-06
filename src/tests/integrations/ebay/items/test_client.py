import random
from datetime import UTC, datetime

from erp.integrations.ebay.items.client import EbayItemClient

# ============================================================================
# COUNT & STRUCTURAL INTEGRITY TESTS
# ============================================================================


def test_get_items_returns_exact_mock_payload_count():
    """
    The client generation loop must strictly deliver exactly 420 payload rows
    to satisfy high-volume frontend performance testing targets.
    """
    client = EbayItemClient()
    dummy_since = datetime.now(tz=UTC)

    items = client.get_items(dummy_since)

    assert isinstance(items, list)
    assert len(items) == 420


def test_get_items_payload_schema_and_value_types():
    """
    Every dictionary item inside the generated collection must strictly adhere
    to the structural schema definition required by downstream adapters.
    """
    client = EbayItemClient()
    items = client.get_items(datetime.now(tz=UTC))

    # Inspect the first item to guarantee structural nested key compliance
    first_item = items[0]

    assert isinstance(first_item, dict)
    assert "sku" in first_item
    assert "availability" in first_item
    assert "product" in first_item
    assert "price" in first_item
    assert "listingId" in first_item
    assert "status" in first_item

    # Type matching on mandatory deep fields
    assert isinstance(first_item["sku"], str)
    assert first_item["sku"].startswith("SKU-")
    assert isinstance(first_item["price"]["value"], str)
    assert first_item["price"]["currency"] == "GBP"


# ============================================================================
# CONDITIONAL DOMAIN LOGIC TESTS
# ============================================================================


def test_get_items_status_conditional_logic_mapping():
    """
    Validates that the status assignment logic cleanly mirrors stock availability:
    - quantity > 0  -> 'ACTIVE'
    - quantity == 0 -> 'OUT_OF_STOCK'
    """
    client = EbayItemClient()
    items = client.get_items(datetime.now(tz=UTC))

    for item in items:
        ship_to_avail = item["availability"]["shipToLocationAvailability"]
        quantity = ship_to_avail["quantity"]
        status = item["status"]

        if quantity > 0:
            assert status == "ACTIVE"
        else:
            assert status == "OUT_OF_STOCK"


# ============================================================================
# DETERMINISTIC REPRODUCIBILITY TESTS
# ============================================================================


def test_get_items_formatting_and_boundaries_via_seeding():
    """
    By freezing the pseudo-random seed generator, we verify that calculations,
    string zero-padding (.zfill), list limits, and float constraints remain bounded.
    """
    client = EbayItemClient()

    # Arrange
    random.seed(42)

    # Act
    items = client.get_items(datetime.now(tz=UTC))

    # Assert
    test_item = items[0]

    assert test_item["sku"] == "SKU-MONITOR-001"
    assert test_item["listingId"] == "2948101001"

    price_val = test_item["price"]["value"]
    assert price_val == "252.20"

    img_url = test_item["product"]["imageUrls"][0]
    assert img_url.endswith("sig=1")

    for item in items:
        numeric_price = float(item["price"]["value"])
        assert 10.0 <= numeric_price <= 999.0
