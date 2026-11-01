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
# MARKETPLACE SCHEMAS
# ==============================================================================


def test_marketplace_item_valid():
    now = datetime.now(UTC)

    item = MarketplaceItem(
        external_id="EBAY-123",
        marketplace="eBay",
        created_at=now,
    )

    assert item.external_id == "EBAY-123"
    assert item.marketplace == "eBay"
    assert item.created_at == now


def test_marketplace_item_missing_required():
    with pytest.raises(ValidationError):
        MarketplaceItem(marketplace="eBay")


def test_marketplace_create_item_valid():
    item = MarketplaceCreateItem(name="Vintage Lamp")

    assert item.name == "Vintage Lamp"


def test_marketplace_create_item_missing_required():
    with pytest.raises(ValidationError):
        MarketplaceCreateItem()


def test_marketplace_create_item_empty_name():
    with pytest.raises(ValidationError):
        MarketplaceCreateItem(name="")


# ==============================================================================
# ITEM CREATE SCHEMA
# ==============================================================================


def test_item_create_valid_all_fields():
    item = ItemCreate(
        title="Industrial Desk",
        sku="FURN-001",
        base_price=45000,
    )

    assert item.title == "Industrial Desk"
    assert item.sku == "FURN-001"
    assert item.base_price == 45000


def test_item_create_default_base_price():
    """base_price defaults to zero when omitted."""
    item = ItemCreate(
        title="Industrial Desk",
        sku="FURN-001",
    )

    assert item.base_price == 0


def test_item_create_missing_title():
    with pytest.raises(ValidationError):
        ItemCreate(sku="FURN-001")


def test_item_create_missing_sku():
    with pytest.raises(ValidationError):
        ItemCreate(title="Industrial Desk")


def test_item_create_missing_both_required_fields():
    with pytest.raises(ValidationError):
        ItemCreate()


def test_item_create_empty_title():
    with pytest.raises(ValidationError):
        ItemCreate(
            title="   ",
            sku="FURN-001",
        )


def test_item_create_empty_sku():
    with pytest.raises(ValidationError):
        ItemCreate(
            title="Industrial Desk",
            sku="   ",
        )


def test_item_create_title_max_length():
    with pytest.raises(ValidationError) as exc_info:
        ItemCreate(
            title="A" * 256,
            sku="FURN-001",
        )

    assert "String should have at most 255 characters" in str(exc_info.value)


def test_item_create_sku_max_length():
    with pytest.raises(ValidationError) as exc_info:
        ItemCreate(
            title="Industrial Desk",
            sku="S" * 101,
        )

    assert "String should have at most 100 characters" in str(exc_info.value)


def test_item_create_base_price_minimum():
    with pytest.raises(ValidationError) as exc_info:
        ItemCreate(
            title="Industrial Desk",
            sku="FURN-001",
            base_price=-1,
        )

    assert "greater than or equal to 0" in str(exc_info.value)


# ==============================================================================
# ITEM UPDATE SCHEMA
# ==============================================================================


def test_item_update_title_only():
    item = ItemUpdate(title="Updated Title")

    assert item.title == "Updated Title"
    assert item.sku is None
    assert item.base_price is None
    assert item.is_deleted is None


def test_item_update_sku_only():
    item = ItemUpdate(sku="UPDATED-SKU")

    assert item.sku == "UPDATED-SKU"
    assert item.title is None
    assert item.base_price is None


def test_item_update_base_price_only():
    item = ItemUpdate(base_price=2500)

    assert item.base_price == 2500
    assert item.title is None
    assert item.sku is None


def test_item_update_is_deleted_only():
    item = ItemUpdate(is_deleted=True)

    assert item.is_deleted is True
    assert item.title is None
    assert item.sku is None
    assert item.base_price is None


def test_item_update_empty_payload():
    """An empty update is valid and changes no fields."""
    item = ItemUpdate()

    assert item.model_dump(exclude_unset=True) == {}


def test_item_update_explicit_null_title():
    with pytest.raises(ValidationError) as exc_info:
        ItemUpdate(title=None)

    assert "title cannot be null" in str(exc_info.value)


def test_item_update_explicit_null_sku():
    with pytest.raises(ValidationError) as exc_info:
        ItemUpdate(sku=None)

    assert "sku cannot be null" in str(exc_info.value)


def test_item_update_explicit_null_base_price():
    with pytest.raises(ValidationError) as exc_info:
        ItemUpdate(base_price=None)

    assert "base_price cannot be null" in str(exc_info.value)


def test_item_update_negative_base_price():
    with pytest.raises(ValidationError):
        ItemUpdate(base_price=-1)


def test_item_update_empty_title():
    with pytest.raises(ValidationError):
        ItemUpdate(title="   ")


def test_item_update_empty_sku():
    with pytest.raises(ValidationError):
        ItemUpdate(sku="   ")


def test_item_update_title_max_length():
    with pytest.raises(ValidationError):
        ItemUpdate(title="A" * 256)


def test_item_update_sku_max_length():
    with pytest.raises(ValidationError):
        ItemUpdate(sku="S" * 101)


def test_item_update_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ItemUpdate(unknown_field="value")


def test_item_update_exclude_unset():
    """Only explicitly provided fields are included in partial updates."""
    item = ItemUpdate(title="Updated Title")

    assert item.model_dump(exclude_unset=True) == {
        "title": "Updated Title",
    }


def test_item_update_explicit_false_is_deleted():
    """Explicit False must not be confused with an omitted field."""
    item = ItemUpdate(is_deleted=False)

    assert item.model_dump(exclude_unset=True) == {
        "is_deleted": False,
    }


# ==============================================================================
# ITEM RESPONSE SCHEMA
# ==============================================================================


def test_item_response_valid():
    now = datetime.now(UTC)
    item_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    response = ItemResponse(
        id=item_id,
        workspace_id=workspace_id,
        title="Ergonomic Chair",
        sku="CHAIR-01",
        base_price=25000,
        barcode_id="1234567890123",
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )

    assert response.id == item_id
    assert response.workspace_id == workspace_id
    assert response.title == "Ergonomic Chair"
    assert response.sku == "CHAIR-01"
    assert response.base_price == 25000
    assert response.stock_movements == []
    assert response.quantity_on_order == 0
    assert response.quantity_allocated == 0
    assert response.total_quantity_on_hand == 0


def test_item_response_default_values():
    """Response metrics and base price have defaults."""
    now = datetime.now(UTC)

    response = ItemResponse(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        title="Test Item",
        sku="TEST-01",
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )

    assert response.base_price == 0
    assert response.quantity_on_order == 0
    assert response.quantity_allocated == 0
    assert response.total_quantity_on_hand == 0
    assert response.stock_movements == []
    assert response.barcode_id is None


def test_item_paginated_response():
    now = datetime.now(UTC)

    item = ItemResponse(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        title="Test Item",
        sku="TEST-01",
        base_price=100,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )

    paginated = ItemPaginatedResponse(
        items=[item],
        total=1,
    )

    assert paginated.total == 1
    assert paginated.page == 1
    assert paginated.limit == 20
    assert len(paginated.items) == 1
    assert paginated.items[0].sku == "TEST-01"
    assert paginated.filters == []


def test_item_paginated_response_empty():
    paginated = ItemPaginatedResponse(
        items=[],
        total=0,
    )

    assert paginated.items == []
    assert paginated.total == 0
    assert paginated.page == 1
    assert paginated.limit == 20


def test_item_response_from_attributes():
    """ItemResponse can be constructed from an ORM-like object."""

    class DummyItemORM:
        def __init__(self):
            self.id = uuid.uuid4()
            self.workspace_id = uuid.uuid4()
            self.title = "ORM Title"
            self.sku = "ORM-SKU"
            self.base_price = 100
            self.barcode_id = "1234567890123"
            self.created_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)
            self.is_deleted = False
            self.quantity_on_order = 5
            self.quantity_allocated = 2
            self.total_quantity_on_hand = 10
            self.stock_movements = []

    orm_obj = DummyItemORM()
    response = ItemResponse.model_validate(orm_obj)

    assert response.id == orm_obj.id
    assert response.title == orm_obj.title
    assert response.sku == orm_obj.sku
    assert response.quantity_on_order == 5
    assert response.quantity_allocated == 2
    assert response.total_quantity_on_hand == 10
