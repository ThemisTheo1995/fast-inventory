from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.erp.api.modules.orders.schemas import (
    MarketplaceCreateOrder,
    MarketplaceCreateOrderItem,
    MarketplaceOrder,
    MarketplaceOrderItem,
)

# ============================================================================
# MARKETPLACE ORDER ITEM TESTS
# ============================================================================


def test_marketplace_order_item_happy_path():
    """
    HAPPY PATH:
    Valid attributes should correctly instantiate a MarketplaceOrderItem
    and execute Pydantic type coercion (e.g., float/string to Decimal).
    """
    item = MarketplaceOrderItem(sku="SKU-CHAIR-01", quantity=3, price="49.99")

    assert item.sku == "SKU-CHAIR-01"
    assert item.quantity == 3
    assert item.price == Decimal("49.99")


@pytest.mark.parametrize(
    "invalid_data",
    [
        {"sku": "SKU-1", "quantity": "not_an_int", "price": 10.00},
        {"sku": "SKU-1", "quantity": 5, "price": "invalid_decimal"},
        {"quantity": 5, "price": 10.00},
    ],
)
def test_marketplace_order_item_validation_errors(invalid_data):
    """
    Providing structurally malformed types or omitting mandatory fields
    must raise a ValidationError.
    """
    with pytest.raises(ValidationError):
        MarketplaceOrderItem(**invalid_data)


# ============================================================================
# MARKETPLACE ORDER TESTS
# ============================================================================


def test_marketplace_order_happy_path():
    """
    HAPPY PATH:
    Verifies that a full order data structure, including nested arrays
    of items and ISO datetime strings, parses smoothly.
    """
    order_data = {
        "external_id": "ORDER-998811",
        "marketplace": "eBay",
        "total": "150.50",
        "currency": "USD",
        "created_at": "2026-05-31T12:00:00Z",
        "items": [{"sku": "SKU-LAMP-02", "quantity": 1, "price": "150.50"}],
    }

    order = MarketplaceOrder(**order_data)

    assert order.external_id == "ORDER-998811"
    assert order.marketplace == "eBay"
    assert order.total == Decimal("150.50")
    assert order.currency == "USD"
    assert order.created_at == datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    assert len(order.items) == 1
    assert order.items[0].sku == "SKU-LAMP-02"


def test_marketplace_order_default_factory_for_items():
    """
    EDGE CASE / DEFAULT PATH:
    If the 'items' key is completely missing from the incoming data,
    the schema default_factory must cleanly fall back to an empty list.
    """
    order = MarketplaceOrder(
        external_id="ORDER-MINIMAL",
        marketplace="Amazon",
        total=Decimal("0.00"),
        currency="EUR",
        created_at=datetime.now(tz=UTC),
    )

    assert order.items == []


# ============================================================================
# MARKETPLACE CREATE ORDER TESTS
# ============================================================================


def test_marketplace_create_order_happy_path():
    """
    HAPPY PATH:
    Validates the intake schema layout used when clients request
    a new order creation event inside the ERP core.
    """
    payload = {
        "total": "89.90",
        "currency": "GBP",
        "items": [
            {"sku": "SKU-SHIRT-M", "quantity": 2, "price": "39.95"},
            {"sku": "SKU-SOCKS-B", "quantity": 1, "price": "10.00"},
        ],
    }

    create_order = MarketplaceCreateOrder(**payload)

    assert create_order.total == Decimal("89.90")
    assert create_order.currency == "GBP"
    assert len(create_order.items) == 2
    assert isinstance(create_order.items[0], MarketplaceCreateOrderItem)
    assert create_order.items[0].sku == "SKU-SHIRT-M"
