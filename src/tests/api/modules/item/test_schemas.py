import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from erp.api.modules.item.schemas import (
    ItemCreate,
    ItemPaginatedResponse,
    ItemResponse,
    ItemUpdate,
    MarketplaceCreateItem,
    MarketplaceItem,
)

# ==============================================================================
# Marketplace Schemas
# ==============================================================================


def test_marketplace_item_valid():
    """Verifies valid marketplace item creation."""
    now = datetime.now(UTC)
    item = MarketplaceItem(external_id="EBAY-123", marketplace="eBay", created_at=now)

    assert item.external_id == "EBAY-123"
    assert item.marketplace == "eBay"
    assert item.created_at == now


def test_marketplace_item_missing_required():
    """Verifies required fields are enforced for MarketplaceItem."""
    with pytest.raises(ValidationError):
        MarketplaceItem(marketplace="eBay")


def test_marketplace_create_item_valid():
    """Verifies valid marketplace create item parsing."""
    item = MarketplaceCreateItem(name="Vintage Lamp")
    assert item.name == "Vintage Lamp"


def test_marketplace_create_item_missing_required():
    """Verifies required fields are enforced for MarketplaceCreateItem."""
    with pytest.raises(ValidationError):
        MarketplaceCreateItem()


# ==============================================================================
# Item Base & Mutations (Create/Update)
# ==============================================================================


def test_item_create_valid_all_fields():
    """Verifies ItemCreate parses valid full payloads."""
    payload = {
        "title": "Industrial Desk",
        "sku": "FURN-001",
        "base_price": 45000,  # Stored in cents, e.g., $450.00
    }
    item = ItemCreate(**payload)

    assert item.title == "Industrial Desk"
    assert item.sku == "FURN-001"
    assert item.base_price == 45000


def test_item_create_optional_fields():
    """Verifies ItemCreate allows missing fields due to None defaults."""
    item = ItemCreate()

    assert item.title is None
    assert item.sku is None
    assert item.base_price is None


def test_item_update_inherits_base():
    """Verifies ItemUpdate behaves identically to ItemCreate/ItemBase."""
    item = ItemUpdate(title="Updated Title")

    assert item.title == "Updated Title"
    assert item.sku is None
    assert item.base_price is None


def test_item_title_max_length():
    """Verifies title enforces the 255 character limit."""
    long_title = "A" * 256

    with pytest.raises(ValidationError) as exc_info:
        ItemCreate(title=long_title)

    assert "String should have at most 255 characters" in str(exc_info.value)


def test_item_sku_max_length():
    """Verifies SKU enforces the 100 character limit."""
    long_sku = "S" * 101

    with pytest.raises(ValidationError) as exc_info:
        ItemCreate(sku=long_sku)

    assert "String should have at most 100 characters" in str(exc_info.value)


def test_item_base_price_minimum():
    """Verifies base_price must be non-negative."""
    with pytest.raises(ValidationError) as exc_info:
        ItemCreate(base_price=-1)

    assert "Input should be greater than or equal to 0" in str(exc_info.value)


# ==============================================================================
# Response Models
# ==============================================================================


def test_item_response_valid():
    """Verifies ItemResponse correctly structures the output payload."""
    now = datetime.now(UTC)
    item_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    payload = {
        "id": item_id,
        "workspace_id": workspace_id,
        "title": "Ergonomic Chair",
        "sku": "CHAIR-01",
        "base_price": 25000,
        "created_at": now,
        "updated_at": now,
    }

    response = ItemResponse(**payload)

    assert response.id == item_id
    assert response.workspace_id == workspace_id
    assert response.title == "Ergonomic Chair"
    assert response.stock_movements == []  # Verifies default_factory kicks in


def test_item_paginated_response():
    """Verifies pagination schema correctly holds items and total."""
    now = datetime.now(UTC)

    item = ItemResponse(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        title="Test Item",
        sku="TEST-01",
        base_price=100,
        created_at=now,
        updated_at=now,
    )

    paginated = ItemPaginatedResponse(items=[item], total=1)

    assert paginated.total == 1
    assert len(paginated.items) == 1
    assert paginated.items[0].sku == "TEST-01"


def test_item_response_from_attributes():
    """Verifies ItemResponse can be created directly from ORM objects."""

    class DummyItemORM:
        def __init__(self):
            self.id = uuid.uuid4()
            self.workspace_id = uuid.uuid4()
            self.title = "ORM Title"
            self.sku = "ORM-SKU"
            self.base_price = 100
            self.created_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)
            self.stock_movements = []

    orm_obj = DummyItemORM()
    response = ItemResponse.model_validate(orm_obj)

    assert response.id == orm_obj.id
    assert response.title == "ORM Title"
