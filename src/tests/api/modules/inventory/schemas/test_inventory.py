from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from erp.api.modules.inventory.schemas.inventory import InventoryResponse

# ==============================================================================
# INVENTORY RESPONSE SCHEMA
# ==============================================================================


def test_inventory_response_valid_data(inventory_data):
    response = InventoryResponse(**inventory_data)

    assert response.id == inventory_data["id"]
    assert response.workspace_id == inventory_data["workspace_id"]
    assert response.item_id == inventory_data["item_id"]
    assert response.bin_id == inventory_data["bin_id"]
    assert response.quantity_on_hand == 25


def test_inventory_response_requires_all_fields(inventory_data):
    required_fields = [
        "id",
        "created_at",
        "updated_at",
        "workspace_id",
        "item_id",
        "bin_id",
        "quantity_on_hand",
    ]

    for field in required_fields:
        invalid_data = inventory_data.copy()
        invalid_data.pop(field)

        with pytest.raises(ValidationError):
            InventoryResponse(**invalid_data)


def test_inventory_response_rejects_invalid_quantity(inventory_data):
    invalid_data = inventory_data.copy()
    invalid_data["quantity_on_hand"] = "not-a-number"

    with pytest.raises(ValidationError):
        InventoryResponse(**invalid_data)


def test_inventory_response_rejects_invalid_uuid(inventory_data):
    invalid_data = inventory_data.copy()
    invalid_data["bin_id"] = "invalid-uuid"

    with pytest.raises(ValidationError):
        InventoryResponse(**invalid_data)


def test_inventory_response_supports_from_attributes(inventory_data):
    """Verifies ORM-style attribute validation."""
    inventory_object = SimpleNamespace(**inventory_data)

    response = InventoryResponse.model_validate(inventory_object)

    assert response.id == inventory_data["id"]
    assert response.item_id == inventory_data["item_id"]
    assert response.bin_id == inventory_data["bin_id"]
    assert response.quantity_on_hand == 25
